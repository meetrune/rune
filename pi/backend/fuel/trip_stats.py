"""Per-trip statistics accumulator.

Called every 10Hz tick during an active trip. Computes rich aggregates
that get stored as a JSON blob alongside the basic trip totals.

These stats power the Trip Summary screen with insights like:
- "You idled for 4.2 minutes, burning $0.18"
- "Engine warmed up in 3 minutes, costing $0.40 in extra fuel"
- "STFT spiked 3 times -- something worth watching"
- "Best MPG: 42.1 on highway. Worst: 6.3 during merge."
"""

from __future__ import annotations

from typing import Any

from backend.obd_manager.models import (
    LITERS_PER_GALLON,
    VehicleSnapshot,
    calculate_instant_mpg,
    maf_to_fuel_rate_lph,
)

# Honda L15BE operating temp threshold
COOLANT_WARM_THRESHOLD_C = 82.0

# Speed threshold matching FuelCalculator
SPEED_THRESHOLD_KPH = 5.0

# RPM threshold for engine running
RPM_ON_THRESHOLD = 50.0

# STFT spike threshold
STFT_SPIKE_THRESHOLD_PCT = 10.0

# MPG averaging window (seconds) -- avoids instantaneous noise
MPG_WINDOW_SAMPLES = 50  # 5 seconds at 10Hz


class TripStatsAccumulator:
    """Accumulates per-trip statistics from 10Hz VehicleSnapshot ticks.

    Call update() every tick. Call finalize() when the trip ends to get
    the stats dict for DB storage.
    """

    def __init__(self) -> None:
        # Idle tracking
        self._idle_seconds: float = 0.0
        self._idle_fuel_gal: float = 0.0

        # Warmup tracking
        self._warmed_up: bool = False
        self._warmup_seconds: float = 0.0
        self._warmup_fuel_gal: float = 0.0

        # MPG tracking (rolling window for stability)
        self._mpg_buffer: list[float] = []
        self._max_mpg: float = 0.0
        self._min_mpg: float = 999.0

        # STFT spike tracking
        self._stft_in_spike: bool = False
        self._stft_spikes: int = 0
        self._max_stft: float = 0.0

        # Peak tracking
        self._peak_load_pct: float = 0.0
        self._peak_rpm: float = 0.0

        # Speed for average
        self._moving_speed_sum: float = 0.0
        self._moving_samples: int = 0

        self._last_timestamp: float | None = None

    def update(self, snap: VehicleSnapshot) -> None:
        """Process one 10Hz tick."""
        now = snap.timestamp
        dt = 0.0
        if self._last_timestamp is not None:
            dt = max(0.0, now - self._last_timestamp)
        self._last_timestamp = now

        if dt <= 0:
            return

        # Fuel this tick
        fuel_rate_lph = maf_to_fuel_rate_lph(snap.maf_gps)
        fuel_gal = (fuel_rate_lph / LITERS_PER_GALLON) * (dt / 3600)

        moving = snap.speed_kph >= SPEED_THRESHOLD_KPH
        engine_on = snap.rpm >= RPM_ON_THRESHOLD

        # --- Idle tracking ---
        if not moving and engine_on:
            self._idle_seconds += dt
            self._idle_fuel_gal += fuel_gal

        # --- Warmup tracking ---
        if not self._warmed_up:
            if snap.coolant_temp_c >= COOLANT_WARM_THRESHOLD_C:
                self._warmed_up = True
            else:
                self._warmup_seconds += dt
                self._warmup_fuel_gal += fuel_gal

        # --- MPG tracking (only while moving) ---
        if moving and snap.maf_gps > 0:
            mpg = calculate_instant_mpg(snap.speed_kph, snap.maf_gps)
            if mpg is not None and mpg > 0:
                self._mpg_buffer.append(mpg)
                if len(self._mpg_buffer) > MPG_WINDOW_SAMPLES:
                    self._mpg_buffer.pop(0)

                # Only update max/min after we have a full window (avoids noise)
                if len(self._mpg_buffer) >= MPG_WINDOW_SAMPLES:
                    avg = sum(self._mpg_buffer) / len(self._mpg_buffer)
                    if avg > self._max_mpg:
                        self._max_mpg = avg
                    if avg < self._min_mpg:
                        self._min_mpg = avg

        # --- STFT spike tracking ---
        stft_abs = abs(snap.stft_pct)
        if stft_abs > self._max_stft:
            self._max_stft = stft_abs

        if stft_abs > STFT_SPIKE_THRESHOLD_PCT:
            if not self._stft_in_spike:
                self._stft_spikes += 1
                self._stft_in_spike = True
        else:
            self._stft_in_spike = False

        # --- Peak tracking ---
        if snap.engine_load_pct > self._peak_load_pct:
            self._peak_load_pct = snap.engine_load_pct
        if snap.rpm > self._peak_rpm:
            self._peak_rpm = snap.rpm

        # --- Average speed (while moving) ---
        if moving:
            self._moving_speed_sum += snap.speed_kph * 0.621371  # to mph
            self._moving_samples += 1

    def finalize(self) -> dict[str, Any]:
        """Return the accumulated stats as a dict for JSON storage."""
        return {
            "idle_seconds": round(self._idle_seconds, 1),
            "idle_fuel_gal": round(self._idle_fuel_gal, 4),
            "warmup_seconds": round(self._warmup_seconds, 1),
            "warmup_fuel_gal": round(self._warmup_fuel_gal, 4),
            "max_mpg": round(self._max_mpg, 1) if 0 < self._max_mpg < 999 else None,
            "min_mpg": round(self._min_mpg, 1) if self._min_mpg < 999 else None,
            "stft_spikes": self._stft_spikes,
            "max_stft": round(self._max_stft, 1),
            "peak_load_pct": round(self._peak_load_pct, 1),
            "peak_rpm": round(self._peak_rpm),
            "avg_speed_mph": round(self._moving_speed_sum / self._moving_samples, 1) if self._moving_samples > 0 else 0,
        }
