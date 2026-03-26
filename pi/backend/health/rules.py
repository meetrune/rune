"""Per-subsystem scoring rules.

Translates raw sensor values into 0-100 health scores using Honda-specific
thresholds. Uses STEPPED deductions matching production fleet scoring systems:
  100  = within normal range
  85   = warning zone (fixed step, actionable threshold)
  50   = at critical threshold
  20   = beyond critical (minimum floor, never 0 unless DTC present)
"""

from __future__ import annotations

from backend.health.thresholds import (
    BATTERY_VOLTAGE,
    CATALYST_TEMP,
    COOLANT_TEMP,
    CVT_FLUID_TEMP,
    ENGINE_LOAD_IDLE,
    IDLE_RPM,
    LTFT,
    OIL_TEMP,
    STFT,
    SUBSYSTEM_WEIGHTS,
    AbsoluteThreshold,
    RangeThreshold,
)
from backend.obd_manager.models import VehicleSnapshot


def score_range(value: float, threshold: RangeThreshold) -> float:
    """Score a value against a range threshold using stepped deductions.

    Returns:
        100.0 if within normal range
        85.0 if in warning zone (between normal and warning/critical boundary)
        50.0 if at critical boundary
        20.0 if beyond critical (floor -- never 0 from thresholds alone)
    """
    # Within normal range
    if threshold.normal_low <= value <= threshold.normal_high:
        return 100.0

    # Check high side
    if value > threshold.normal_high:
        if value <= threshold.warning_high:
            return 85.0
        if value <= threshold.critical_high:
            return 50.0
        return 20.0

    # Check low side
    if value < threshold.normal_low:
        if value >= threshold.warning_low:
            return 85.0
        if value >= threshold.critical_low:
            return 50.0
        return 20.0

    return 100.0


def score_absolute(value: float, threshold: AbsoluteThreshold) -> float:
    """Score a value where absolute deviation matters (fuel trims).

    Same stepped approach:
        100.0 if within normal
        85.0 if in warning zone
        50.0 if at critical
        20.0 if beyond critical
    """
    abs_val = abs(value)

    if abs_val <= threshold.normal:
        return 100.0

    if abs_val <= threshold.warning:
        return 85.0

    if abs_val <= threshold.critical:
        return 50.0

    return 20.0


def score_subsystems(snap: VehicleSnapshot) -> dict[str, float]:
    """Score all six subsystems from a VehicleSnapshot. Returns dict of 0-100 scores."""
    scores: dict[str, float] = {}

    # Engine: RPM-at-idle check + load-at-idle check
    # Only applies when engine is actually running AND car is stopped.
    # RPM < 50 = engine off (not a health issue, just turned off).
    # During driving (speed > 5 kph), RPM and load vary widely -- skip threshold checks.
    is_idle = snap.speed_kph < 5
    engine_running = snap.rpm >= 50
    if is_idle and engine_running:
        rpm_score = score_range(snap.rpm, IDLE_RPM)
        load_score = score_range(snap.engine_load_pct, ENGINE_LOAD_IDLE)
        scores["engine"] = (rpm_score + load_score) / 2
    else:
        # Engine off or driving -- anomaly detection handles issues
        scores["engine"] = 100.0

    # Transmission: CVT fluid temp (if available)
    if snap.cvt_fluid_temp_c is not None:
        scores["transmission"] = score_range(snap.cvt_fluid_temp_c, CVT_FLUID_TEMP)
    else:
        scores["transmission"] = 100.0  # no data = assume healthy

    # Fuel: short-term and long-term fuel trims
    stft_score = score_absolute(snap.stft_pct, STFT)
    ltft_score = score_absolute(snap.ltft_pct, LTFT)
    scores["fuel"] = (stft_score + ltft_score) / 2

    # Cooling: coolant + oil temp
    coolant_score = score_range(snap.coolant_temp_c, COOLANT_TEMP)
    oil_score = score_range(snap.oil_temp_c, OIL_TEMP)
    scores["cooling"] = (coolant_score + oil_score) / 2

    # Exhaust: catalyst temp
    scores["exhaust"] = score_range(snap.catalyst_temp_c, CATALYST_TEMP)

    # Electrical: battery voltage
    scores["electrical"] = score_range(snap.battery_voltage, BATTERY_VOLTAGE)

    return scores


def compute_overall(subsystem_scores: dict[str, float]) -> float:
    """Compute weighted overall health score from subsystem scores."""
    total = 0.0
    for subsystem, weight in SUBSYSTEM_WEIGHTS.items():
        score = subsystem_scores.get(subsystem, 100.0)
        total += score * weight
    return max(0.0, min(100.0, total))
