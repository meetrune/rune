"""Adaptive thermal management for Rune's Pi 4B.

Uses production-proven strategies from OpenPilot (comma.ai) adapted
for a Raspberry Pi 4B running in a car armrest compartment.

Key design principles:
  1. Overlapping thermal bands with hysteresis (prevents oscillation)
  2. IIR low-pass filter on temperature (prevents noise-triggered transitions)
  3. Rate-of-change detection (catches fast rises before hitting limits)
  4. Ambient-relative thresholds (hot parking lot = tighter limits)
  5. Multi-level response (reduce work before shutdown)

Pi 4B thermal facts (verified):
  - Throttle starts at 80C junction (clock reduced)
  - Hard throttle at 85C (drops to ~428 MHz = 71% loss)
  - Enclosed case delta: +35-50C above ambient
  - Official ambient max: 50C

Sources:
  - OpenPilot hardwared.py thermal bands
  - OpenPilot filter_simple.py IIR implementation
  - Pi 4B datasheet RP-008341-DS (0C to 50C ambient)
  - Martin Rowan enclosed case measurements (78C idle at 21C ambient)
  - Stanford/ASU parked car temperature studies
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ThermalStatus(Enum):
    """Thermal state of the Pi. Each level has specific actions."""
    GREEN = "green"     # Full operation
    YELLOW = "yellow"   # Warning, log it
    ORANGE = "orange"   # Reduce workload (drop to 5Hz, skip ML)
    RED = "red"         # Critical (drop to 2Hz, minimal PIDs only)
    DANGER = "danger"   # Shutdown immediately


@dataclass(frozen=True)
class ThermalBand:
    """A thermal band with entry and exit thresholds (hysteresis).

    To ENTER this band: temperature must reach entry_temp.
    To EXIT downward: temperature must drop below exit_temp.
    The gap (entry_temp - exit_temp) is the hysteresis.
    """
    entry_temp: float    # must reach this to enter (going up)
    exit_temp: float     # must drop below this to leave (going down)


# Thermal bands for Pi CPU temperature.
# Overlapping ranges prevent oscillation (OpenPilot pattern).
#
# Pi 4B throttles at 80C, hard-throttles at 85C.
# Our bands trigger BEFORE hardware throttling kicks in.
#
# Sources:
#   - Pi 4B throttle: 80C (Raspberry Pi Foundation documentation)
#   - Pi 4B hard throttle: 85C (vcgencmd get_throttled bit flags)
#   - OpenPilot: green<80, yellow 75-96, red 88-107, danger>94
#   - Adapted for Pi (lower limits than Qualcomm SoC in OpenPilot)
CPU_THERMAL_BANDS: dict[ThermalStatus, ThermalBand] = {
    ThermalStatus.GREEN:  ThermalBand(entry_temp=0,    exit_temp=0),     # default state
    ThermalStatus.YELLOW: ThermalBand(entry_temp=65.0, exit_temp=60.0),  # 5C hysteresis
    ThermalStatus.ORANGE: ThermalBand(entry_temp=72.0, exit_temp=65.0),  # 7C hysteresis
    ThermalStatus.RED:    ThermalBand(entry_temp=78.0, exit_temp=72.0),  # 6C hysteresis
    ThermalStatus.DANGER: ThermalBand(entry_temp=83.0, exit_temp=76.0),  # 7C hysteresis
}

# Armrest temperature bands.
# Armrest temp determines whether the Pi should even be running.
#
# Sources:
#   - ASU study: 65C cabin air in 43C ambient after 1h sun
#   - Pi 4B official ambient max: 50C
#   - Pi enclosed delta: +35-50C above ambient
#   - At 55C armrest + 40C delta = 95C junction (past hard throttle)
ARMREST_THERMAL_BANDS: dict[ThermalStatus, ThermalBand] = {
    ThermalStatus.GREEN:  ThermalBand(entry_temp=0,    exit_temp=0),
    ThermalStatus.YELLOW: ThermalBand(entry_temp=40.0, exit_temp=35.0),  # getting warm
    ThermalStatus.ORANGE: ThermalBand(entry_temp=48.0, exit_temp=42.0),  # above Pi spec
    ThermalStatus.RED:    ThermalBand(entry_temp=55.0, exit_temp=48.0),  # Pi will throttle
    ThermalStatus.DANGER: ThermalBand(entry_temp=62.0, exit_temp=54.0),  # shutdown
}

# Rate-of-change thresholds (degrees C per minute)
# Source: fire detection standard = 8.3C/min, MIL-STD-810G stabilization = 2C/hr
RATE_NORMAL = 2.0     # normal warmup
RATE_WARNING = 5.0    # aggressive rise, preemptive action
RATE_CRITICAL = 10.0  # something wrong (blocked airflow, hardware fault)

# Cold temperature floor -- don't boot below this
# Source: standard SD card rated 0C, industrial -25C
# Pi SoC rated to -40C but SD card is the weak link
COLD_BOOT_FLOOR_C = -10.0  # conservative, assuming industrial SD card

# IIR filter time constant (seconds)
# Source: OpenPilot uses tau=5s for temperature smoothing
# A spike takes ~15s (3*tau) to fully register, preventing noise triggers
IIR_TAU = 5.0


@dataclass
class WelfordTracker:
    """Online mean + stddev using Welford's algorithm.

    O(1) memory, no history buffer. Tracks what's "normal" for a
    given metric over time.

    Source: Welford (1962), "Note on a method for calculating
    corrected sums of squares and products"
    """
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def update(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (x - self.mean)

    @property
    def variance(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def stddev(self) -> float:
        return float(self.variance ** 0.5)

    def z_score(self, x: float) -> float:
        """How many standard deviations x is from the mean."""
        if self.stddev <= 0 or self.n < 30:
            return 0.0
        return (x - self.mean) / self.stddev


@dataclass
class ThermalState:
    """Current thermal assessment of the system."""
    cpu_status: ThermalStatus = ThermalStatus.GREEN
    armrest_status: ThermalStatus = ThermalStatus.GREEN
    overall_status: ThermalStatus = ThermalStatus.GREEN
    cpu_temp_filtered: float = 0.0
    armrest_temp_filtered: float = 0.0
    cpu_rate_per_min: float = 0.0
    armrest_rate_per_min: float = 0.0
    recommended_ws_hz: int = 10
    should_shutdown: bool = False
    message: str = ""


class ThermalManager:
    """Adaptive thermal management for Rune.

    Call update() once per second with current temperatures.
    It returns a ThermalState with the current assessment and
    recommended actions.
    """

    def __init__(self) -> None:
        # IIR-filtered temperatures
        self._cpu_filtered: float | None = None
        self._armrest_filtered: float | None = None

        # Band state (with hysteresis)
        self._cpu_status = ThermalStatus.GREEN
        self._armrest_status = ThermalStatus.GREEN

        # Rate-of-change tracking (60-second window, 1Hz samples)
        self._cpu_history: deque[tuple[float, float]] = deque(maxlen=60)
        self._armrest_history: deque[tuple[float, float]] = deque(maxlen=60)

        # Welford trackers for baseline learning
        self._cpu_baseline = WelfordTracker()
        self._armrest_baseline = WelfordTracker()
        self._vin_baseline = WelfordTracker()

        # Startup ambient (recorded in first 10 seconds)
        self._startup_ambient: float | None = None
        self._startup_samples: list[float] = []
        self._startup_complete = False

        self._last_update = time.time()

    def update(
        self,
        cpu_temp_c: float | None,
        armrest_temp_c: float | None,
        vin_voltage: float | None = None,
        _now: float | None = None,
    ) -> ThermalState:
        """Process new temperature readings and return thermal assessment.

        Call this once per second (not at 10Hz -- thermal changes are slow).
        _now is for testing only -- overrides time.time().
        """
        now = _now if _now is not None else time.time()
        dt = now - self._last_update
        self._last_update = now

        # Clamp dt to prevent huge jumps after sleep/pause
        dt = min(dt, 5.0)

        state = ThermalState()

        # --- Record startup ambient (first 10 seconds) ---
        if not self._startup_complete and armrest_temp_c is not None:
            self._startup_samples.append(armrest_temp_c)
            if len(self._startup_samples) >= 10:
                self._startup_ambient = sum(self._startup_samples) / len(self._startup_samples)
                self._startup_complete = True
                logger.info("Startup ambient recorded: %.1fC", self._startup_ambient)

        # --- IIR low-pass filter ---
        # alpha = dt / (tau + dt), matching OpenPilot's filter_simple.py
        alpha = dt / (IIR_TAU + dt)

        if cpu_temp_c is not None:
            if self._cpu_filtered is None:
                self._cpu_filtered = cpu_temp_c
            else:
                self._cpu_filtered = (1 - alpha) * self._cpu_filtered + alpha * cpu_temp_c
            state.cpu_temp_filtered = self._cpu_filtered
            self._cpu_history.append((now, self._cpu_filtered))
            self._cpu_baseline.update(cpu_temp_c)

        if armrest_temp_c is not None:
            if self._armrest_filtered is None:
                self._armrest_filtered = armrest_temp_c
            else:
                self._armrest_filtered = (1 - alpha) * self._armrest_filtered + alpha * armrest_temp_c
            state.armrest_temp_filtered = self._armrest_filtered
            self._armrest_history.append((now, self._armrest_filtered))
            self._armrest_baseline.update(armrest_temp_c)

        if vin_voltage is not None:
            self._vin_baseline.update(vin_voltage)

        # --- Rate of change (linear regression over history) ---
        state.cpu_rate_per_min = self._compute_rate(self._cpu_history)
        state.armrest_rate_per_min = self._compute_rate(self._armrest_history)

        # --- Band transitions with hysteresis ---
        if self._cpu_filtered is not None:
            self._cpu_status = self._evaluate_band(
                self._cpu_filtered, self._cpu_status, CPU_THERMAL_BANDS,
            )
        if self._armrest_filtered is not None:
            self._armrest_status = self._evaluate_band(
                self._armrest_filtered, self._armrest_status, ARMREST_THERMAL_BANDS,
            )

        # Rate-of-change can escalate status by one level
        # Use list index for comparison (string enum values don't sort correctly)
        status_order = list(ThermalStatus)
        if state.cpu_rate_per_min > RATE_CRITICAL:
            self._cpu_status = self._escalate(self._cpu_status)
        elif state.cpu_rate_per_min > RATE_WARNING:
            if status_order.index(self._cpu_status) < status_order.index(ThermalStatus.ORANGE):
                self._cpu_status = ThermalStatus.YELLOW

        state.cpu_status = self._cpu_status
        state.armrest_status = self._armrest_status

        # --- Overall status = worst of CPU and armrest ---
        all_statuses = [self._cpu_status, self._armrest_status]
        status_order = list(ThermalStatus)
        state.overall_status = max(all_statuses, key=lambda s: status_order.index(s))

        # --- Recommended actions ---
        state.recommended_ws_hz = {
            ThermalStatus.GREEN: 10,
            ThermalStatus.YELLOW: 10,
            ThermalStatus.ORANGE: 5,
            ThermalStatus.RED: 2,
            ThermalStatus.DANGER: 0,
        }[state.overall_status]

        state.should_shutdown = state.overall_status == ThermalStatus.DANGER
        state.message = self._build_message(state)

        return state

    def get_voltage_z_score(self, vin: float) -> float:
        """Check how anomalous the current voltage is vs learned baseline."""
        return self._vin_baseline.z_score(vin)

    def get_debug_state(self) -> dict[str, object]:
        """Debug info for the /api/debug endpoint."""
        return {
            "cpu_status": self._cpu_status.value,
            "armrest_status": self._armrest_status.value,
            "cpu_filtered": round(self._cpu_filtered or 0, 1),
            "armrest_filtered": round(self._armrest_filtered or 0, 1),
            "startup_ambient": round(self._startup_ambient or 0, 1),
            "cpu_baseline_mean": round(self._cpu_baseline.mean, 1),
            "cpu_baseline_stddev": round(self._cpu_baseline.stddev, 1),
            "vin_baseline_mean": round(self._vin_baseline.mean, 2),
            "vin_baseline_stddev": round(self._vin_baseline.stddev, 3),
            "vin_samples": self._vin_baseline.n,
        }

    @staticmethod
    def _compute_rate(history: deque[tuple[float, float]]) -> float:
        """Compute rate of temperature change (C/min) using linear regression.

        More robust than simple first/last delta -- a single noisy sample
        won't produce a false alarm.
        """
        n = len(history)
        if n < 10:
            return 0.0

        # Linear regression: slope of temp vs time
        sum_t = sum_temp = sum_t2 = sum_t_temp = 0.0
        for t, temp in history:
            sum_t += t
            sum_temp += temp
            sum_t2 += t * t
            sum_t_temp += t * temp

        denom = n * sum_t2 - sum_t * sum_t
        if abs(denom) < 1e-10:
            return 0.0

        slope_per_sec = (n * sum_t_temp - sum_t * sum_temp) / denom
        return slope_per_sec * 60.0  # convert to C/min

    @staticmethod
    def _evaluate_band(
        temp: float,
        current_status: ThermalStatus,
        bands: dict[ThermalStatus, ThermalBand],
    ) -> ThermalStatus:
        """Evaluate which thermal band the temperature falls in.

        Uses hysteresis: going UP requires reaching entry_temp,
        going DOWN requires dropping below exit_temp.
        """
        status_order = list(ThermalStatus)
        current_idx = status_order.index(current_status)

        # Check if we should escalate (go up)
        for i in range(current_idx + 1, len(status_order)):
            candidate = status_order[i]
            band = bands[candidate]
            if temp >= band.entry_temp:
                return candidate

        # Check if we should de-escalate (go down)
        if current_status != ThermalStatus.GREEN:
            current_band = bands[current_status]
            if temp < current_band.exit_temp:
                # Drop one level (not straight to green -- gradual recovery)
                return status_order[max(0, current_idx - 1)]

        return current_status

    @staticmethod
    def _escalate(status: ThermalStatus) -> ThermalStatus:
        """Move one level up in severity."""
        order = list(ThermalStatus)
        idx = order.index(status)
        if idx < len(order) - 1:
            return order[idx + 1]
        return status

    @staticmethod
    def _build_message(state: ThermalState) -> str:
        """Build Rune-voice message for thermal state."""
        match state.overall_status:
            case ThermalStatus.GREEN:
                return ""
            case ThermalStatus.YELLOW:
                if state.armrest_status == ThermalStatus.YELLOW:
                    return f"Getting warm in here. Armrest at {state.armrest_temp_filtered:.0f} degrees."
                return f"CPU running warm at {state.cpu_temp_filtered:.0f} degrees. Not a problem yet."
            case ThermalStatus.ORANGE:
                return (
                    f"Running hot. Dropping to {state.recommended_ws_hz}Hz to cool down. "
                    f"CPU {state.cpu_temp_filtered:.0f}C, armrest {state.armrest_temp_filtered:.0f}C."
                )
            case ThermalStatus.RED:
                return (
                    f"Too hot. Minimal operation mode. "
                    f"CPU {state.cpu_temp_filtered:.0f}C, armrest {state.armrest_temp_filtered:.0f}C. "
                    f"I'll shut down if this keeps up."
                )
            case ThermalStatus.DANGER:
                return "Shutting down to protect myself. It's too hot in here."
