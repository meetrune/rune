"""Fill-up detector.

Watches fuel_level_pct for jumps >20% between consecutive readings.
When detected, calculates gallons added and generates Rune's fill-up message.

The caller passes in miles_since_last_fill (from the database) so this
class stays testable without any DB dependency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.obd_manager.models import VehicleSnapshot

logger = logging.getLogger(__name__)

FILLUP_THRESHOLD_PCT = 20.0


@dataclass
class FillupEvent:
    """Emitted when a fill-up is detected."""
    detected_at: float  # unix timestamp
    fuel_level_before: float
    fuel_level_after: float
    estimated_gallons: float
    cost_usd: float | None
    mpg_since_last_fill: float | None
    rune_message: str


FILLUP_CONFIRM_READINGS = 3  # require 3 consecutive high readings to confirm


class FillupDetector:
    """Detects fill-up events by watching fuel level jumps.

    Uses multi-sample confirmation: a fuel level jump must persist for
    FILLUP_CONFIRM_READINGS consecutive readings to be confirmed as a
    real fill-up. This prevents false positives from sensor noise
    (fuel slosh on hills, OBD glitches).
    """

    def __init__(
        self,
        tank_capacity_gal: float,
        gas_price_per_gallon: float,
        epa_combined_mpg: float,
    ) -> None:
        self._tank_gal = tank_capacity_gal
        self._gas_price = gas_price_per_gallon
        self._epa_mpg = epa_combined_mpg
        self._last_fuel_pct: float | None = None
        self._readings_since_init: int = 0
        # Multi-sample confirmation state
        self._pending_fillup_from: float | None = None  # fuel level before suspected jump
        self._confirm_count: int = 0

    def check(
        self,
        snap: VehicleSnapshot,
        miles_since_last_fill: float | None = None,
    ) -> FillupEvent | None:
        """Check if a fill-up occurred. Returns FillupEvent or None."""
        current_pct = snap.fuel_level_pct
        event: FillupEvent | None = None

        # Ignore the first 5 readings after init -- OBD can return garbage
        # values during ELM327 protocol negotiation
        self._readings_since_init += 1
        if self._readings_since_init < 5:
            self._last_fuel_pct = current_pct
            return None

        if self._last_fuel_pct is not None:
            delta = current_pct - self._last_fuel_pct

            if delta >= FILLUP_THRESHOLD_PCT:
                # Possible fill-up -- start or continue confirmation
                if self._pending_fillup_from is None:
                    self._pending_fillup_from = self._last_fuel_pct
                    self._confirm_count = 1
                else:
                    self._confirm_count += 1
            elif self._pending_fillup_from is not None:
                # Fuel level dropped back down -- was noise, reset
                if current_pct < self._pending_fillup_from + FILLUP_THRESHOLD_PCT:
                    self._pending_fillup_from = None
                    self._confirm_count = 0
                else:
                    # Still above threshold, count it
                    self._confirm_count += 1

        # Confirmed fill-up after enough consecutive high readings
        if self._confirm_count >= FILLUP_CONFIRM_READINGS and self._pending_fillup_from is not None:
            delta = current_pct - self._pending_fillup_from
            estimated_gal = (delta / 100) * self._tank_gal
            cost = estimated_gal * self._gas_price

            mpg: float | None = None
            if miles_since_last_fill is not None and estimated_gal > 0:
                mpg = miles_since_last_fill / estimated_gal

            message = self._build_message(estimated_gal, current_pct, mpg)

            event = FillupEvent(
                detected_at=snap.timestamp,
                fuel_level_before=self._pending_fillup_from,
                fuel_level_after=current_pct,
                estimated_gallons=round(estimated_gal, 1),
                cost_usd=round(cost, 2),
                mpg_since_last_fill=round(mpg, 1) if mpg else None,
                rune_message=message,
            )
            logger.info("Fill-up detected: %s", message)

            # Reset confirmation state
            self._pending_fillup_from = None
            self._confirm_count = 0

        self._last_fuel_pct = current_pct
        return event

    def _build_message(
        self,
        estimated_gallons: float,
        fuel_level_after: float,
        mpg_since_last_fill: float | None,
    ) -> str:
        """Generate Rune's fill-up message."""
        if fuel_level_after >= 95:
            fill_desc = "Full tank"
        else:
            fill_desc = "Topped off"

        msg = f"{fill_desc}. {estimated_gallons:.1f} gallons back in me."

        if mpg_since_last_fill is not None:
            epa_delta = mpg_since_last_fill - self._epa_mpg
            if abs(epa_delta) < 2:
                qualifier = "right where I should be"
            elif epa_delta > 0:
                qualifier = "above average for me"
            else:
                qualifier = "below average -- worth watching"
            msg += f" {mpg_since_last_fill:.1f} MPG since last fill -- {qualifier}."

        return msg
