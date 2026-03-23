"""Per-subsystem scoring rules.

Translates raw sensor values into 0-100 health scores using the
Honda-specific thresholds. Each parameter gets its own score,
subsystem scores are averaged, and overall is weighted.

Scoring zones:
  100       = within normal range
  70-99     = warning zone (proportional to severity)
  0-69      = critical zone (proportional to severity)
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
    """Score a value against a range threshold. Returns 0-100."""
    # Within normal range
    if threshold.normal_low <= value <= threshold.normal_high:
        return 100.0

    # Warning zone (high side)
    if threshold.normal_high < value <= threshold.warning_high:
        span = threshold.warning_high - threshold.normal_high
        if span <= 0:
            return 85.0
        progress = (value - threshold.normal_high) / span
        return 100.0 - progress * 30.0  # 100 -> 70

    # Warning zone (low side)
    if threshold.warning_low <= value < threshold.normal_low:
        span = threshold.normal_low - threshold.warning_low
        if span <= 0:
            return 85.0
        progress = (threshold.normal_low - value) / span
        return 100.0 - progress * 30.0

    # Critical zone (high side)
    if value > threshold.warning_high:
        span = threshold.critical_high - threshold.warning_high
        if span <= 0:
            return 20.0
        progress = min((value - threshold.warning_high) / span, 1.0)
        return 70.0 - progress * 70.0  # 70 -> 0

    # Critical zone (low side)
    if value < threshold.warning_low:
        span = threshold.warning_low - threshold.critical_low
        if span <= 0:
            return 20.0
        progress = min((threshold.warning_low - value) / span, 1.0)
        return 70.0 - progress * 70.0

    return 100.0


def score_absolute(value: float, threshold: AbsoluteThreshold) -> float:
    """Score a value where absolute deviation matters (fuel trims)."""
    abs_val = abs(value)

    if abs_val <= threshold.normal:
        return 100.0

    if abs_val <= threshold.warning:
        span = threshold.warning - threshold.normal
        if span <= 0:
            return 85.0
        progress = (abs_val - threshold.normal) / span
        return 100.0 - progress * 30.0  # 100 -> 70

    if abs_val <= threshold.critical:
        span = threshold.critical - threshold.warning
        if span <= 0:
            return 35.0
        progress = (abs_val - threshold.warning) / span
        return 70.0 - progress * 70.0  # 70 -> 0

    return 0.0


def score_subsystems(snap: VehicleSnapshot) -> dict[str, float]:
    """Score all six subsystems from a VehicleSnapshot. Returns dict of 0-100 scores."""
    scores: dict[str, float] = {}

    # Engine: RPM-at-idle check + load-at-idle check
    # During driving (speed > 5 kph), RPM and load vary widely -- skip threshold checks
    is_idle = snap.speed_kph < 5
    if is_idle:
        rpm_score = score_range(snap.rpm, IDLE_RPM)
        load_score = score_range(snap.engine_load_pct, ENGINE_LOAD_IDLE)
        scores["engine"] = (rpm_score + load_score) / 2
    else:
        # While driving, engine score is based on RPM stability
        # (anomaly detection handles driving-mode issues)
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
