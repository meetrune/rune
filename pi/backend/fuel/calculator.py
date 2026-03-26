"""Trip fuel calculator.

Tracks fuel consumption and distance over each driving session.
Called on every 10Hz tick, accumulates trip state. The caller
(producer loop in main.py) handles DB writes.

Trip detection:
  START: speed > 5 kph (filters GPS jitter at 1-3 kph)
  END:   RPM drops to 0 (engine off) for 10 seconds.
         RPM is the primary signal -- engine running = trip active.
         Speed-based idle timeout (5 min) is the fallback for RPM glitches.
         This way traffic, red lights, and train crossings never end a trip.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.obd_manager.models import (
    FuelSnapshot,
    KPH_TO_MPH,
    LITERS_PER_GALLON,
    VehicleSnapshot,
    calculate_idle_gph,
    calculate_instant_mpg,
    maf_to_fuel_rate_lph,
)

logger = logging.getLogger(__name__)

# Speed threshold for trip start -- above GPS jitter noise
SPEED_THRESHOLD_KPH = 5.0

# RPM threshold for "engine running" -- idle is 650-750 on the L15BE
# Below this for sustained period = engine is off
RPM_OFF_THRESHOLD = 50.0

# How long RPM must stay at 0 before trip ends (filters momentary dips)
ENGINE_OFF_TIMEOUT_S = 10.0

# Fallback: if RPM data glitches but speed is 0 for this long, end trip anyway
SPEED_IDLE_FALLBACK_TIMEOUT_S = 300.0  # 5 minutes

# Minimum trip distance to be considered real (not noise)
MIN_TRIP_DISTANCE_MI = 0.05  # ~260 feet


@dataclass
class TripState:
    """Mutable accumulator for an active trip."""
    trip_id: int | None  # None until DB assigns ID
    start_time: float
    distance_miles: float
    fuel_gallons: float
    engine_off_since: float | None   # timestamp when RPM dropped to ~0
    speed_idle_since: float | None   # timestamp when speed dropped below threshold


class FuelCalculator:
    """Accumulates fuel and distance over driving sessions.

    Call update() on every tick. It returns a FuelSnapshot plus
    flags indicating trip start/end events.

    Primary trip end signal: RPM = 0 (engine off) for 10 seconds.
    Fallback: speed = 0 for 5 minutes (handles RPM sensor failure).
    """

    def __init__(
        self,
        tank_capacity_gal: float,
        gas_price_per_gallon: float,
    ) -> None:
        self._tank_capacity = tank_capacity_gal
        self._gas_price = gas_price_per_gallon
        self._trip: TripState | None = None
        self._completed_trip: TripState | None = None
        self._last_update_time: float | None = None

    @property
    def is_trip_active(self) -> bool:
        return self._trip is not None

    @property
    def current_trip(self) -> TripState | None:
        return self._trip

    def _end_trip(self, reason: str) -> bool:
        """End the current trip. Returns True if trip was real, False if junk."""
        if self._trip is None:
            return False

        if self._trip.distance_miles < MIN_TRIP_DISTANCE_MI:
            logger.debug(
                "Discarding junk trip: %.4f mi (below %.2f threshold)",
                self._trip.distance_miles, MIN_TRIP_DISTANCE_MI,
            )
            self._trip = None
            return False

        self._completed_trip = self._trip
        self._trip = None
        logger.info(
            "Trip ended (%s): %.2f mi, %.3f gal",
            reason, self._completed_trip.distance_miles, self._completed_trip.fuel_gallons,
        )
        return True

    def update(self, snap: VehicleSnapshot) -> tuple[FuelSnapshot, bool, bool]:
        """Process one VehicleSnapshot tick.

        Returns:
            (fuel_snapshot, trip_started, trip_ended)
        """
        now = snap.timestamp
        trip_started = False
        trip_ended = False

        # Calculate dt (guard against first call and negative dt)
        dt = 0.0
        if self._last_update_time is not None:
            dt = max(0.0, now - self._last_update_time)

        # Fuel consumed this tick
        fuel_rate_lph = maf_to_fuel_rate_lph(snap.maf_gps)
        fuel_this_tick_gal = (fuel_rate_lph / LITERS_PER_GALLON) * (dt / 3600)

        # Distance this tick
        speed_mph = snap.speed_kph * KPH_TO_MPH
        distance_this_tick_mi = speed_mph * (dt / 3600)

        moving = snap.speed_kph >= SPEED_THRESHOLD_KPH
        engine_running = snap.rpm >= RPM_OFF_THRESHOLD

        # --- Trip start: speed above threshold ---
        if moving and self._trip is None:
            self._trip = TripState(
                trip_id=None,
                start_time=now,
                distance_miles=0.0,
                fuel_gallons=0.0,
                engine_off_since=None,
                speed_idle_since=None,
            )
            self._completed_trip = None
            trip_started = True
            logger.info("Trip started")

        # --- Accumulate into active trip ---
        if self._trip is not None:
            self._trip.distance_miles += distance_this_tick_mi
            self._trip.fuel_gallons += fuel_this_tick_gal

            # PRIMARY: Engine off detection (RPM near 0)
            if not engine_running:
                if self._trip.engine_off_since is None:
                    self._trip.engine_off_since = now
                elif now - self._trip.engine_off_since >= ENGINE_OFF_TIMEOUT_S:
                    trip_ended = self._end_trip("engine_off")
            else:
                # Engine is running -- reset the off timer
                if self._trip is not None:
                    self._trip.engine_off_since = None

            # FALLBACK: Speed idle timeout (handles RPM sensor failure)
            if self._trip is not None:
                if not moving:
                    if self._trip.speed_idle_since is None:
                        self._trip.speed_idle_since = now
                    elif now - self._trip.speed_idle_since >= SPEED_IDLE_FALLBACK_TIMEOUT_S:
                        trip_ended = self._end_trip("speed_idle_fallback")
                else:
                    self._trip.speed_idle_since = None

        # Build FuelSnapshot
        instant_mpg = calculate_instant_mpg(snap.speed_kph, snap.maf_gps)
        idle_gph = calculate_idle_gph(snap.maf_gps) if not moving else None

        trip = self._trip or self._completed_trip
        fuel_snap = FuelSnapshot(
            instant_mpg=instant_mpg,
            idle_gph=idle_gph,
            trip_fuel_gal=trip.fuel_gallons if trip else 0.0,
            trip_cost_usd=(trip.fuel_gallons * self._gas_price) if trip else 0.0,
            trip_distance_mi=trip.distance_miles if trip else 0.0,
            tank_pct=snap.fuel_level_pct,
        )

        self._last_update_time = now
        return fuel_snap, trip_started, trip_ended

    def get_completed_trip_summary(self) -> dict[str, Any] | None:
        """Get summary of the just-completed trip.

        Only valid after update() returned trip_ended=True.
        """
        if self._completed_trip is None:
            return None

        t = self._completed_trip
        avg_mpg: float | None = None
        if t.fuel_gallons > 0:
            avg_mpg = t.distance_miles / t.fuel_gallons

        return {
            "trip_id": t.trip_id,
            "start_time": t.start_time,
            "distance_miles": t.distance_miles,
            "fuel_gallons": t.fuel_gallons,
            "fuel_cost_usd": t.fuel_gallons * self._gas_price,
            "avg_mpg": avg_mpg,
        }
