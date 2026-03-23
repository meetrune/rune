"""Honda Accord 2026 SE normal/warning/critical operating ranges.

These values come from ISO 15031-5 PID specifications and Honda
service manual data. They define what "healthy" looks like for
this specific car.

Each parameter has three zones:
- Normal: everything is fine, score stays at 100
- Warning: something to watch, score drops proportionally (70-99)
- Critical: needs attention, score drops below 70
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RangeThreshold:
    """Threshold for a parameter with a normal range (low-high)."""
    normal_low: float
    normal_high: float
    warning_low: float
    warning_high: float
    critical_low: float
    critical_high: float


@dataclass(frozen=True)
class AbsoluteThreshold:
    """Threshold for a parameter where deviation from zero matters (fuel trims)."""
    normal: float      # absolute value within this is normal
    warning: float     # absolute value within this is warning
    critical: float    # absolute value beyond this is critical


# --- Honda Accord 2026 SE Operating Ranges ---

COOLANT_TEMP = RangeThreshold(
    normal_low=82, normal_high=96,
    warning_low=60, warning_high=104,
    critical_low=40, critical_high=110,
)

OIL_TEMP = RangeThreshold(
    normal_low=80, normal_high=100,
    warning_low=50, warning_high=115,
    critical_low=30, critical_high=130,
)

IDLE_RPM = RangeThreshold(
    normal_low=650, normal_high=750,
    warning_low=500, warning_high=900,
    critical_low=400, critical_high=1000,
)

BATTERY_VOLTAGE = RangeThreshold(
    normal_low=13.5, normal_high=14.5,
    warning_low=13.0, warning_high=15.0,
    critical_low=12.8, critical_high=15.2,
)

ENGINE_LOAD_IDLE = RangeThreshold(
    normal_low=15, normal_high=30,
    warning_low=5, warning_high=45,
    critical_low=0, critical_high=50,
)

CVT_FLUID_TEMP = RangeThreshold(
    normal_low=60, normal_high=95,
    warning_low=40, warning_high=115,
    critical_low=20, critical_high=120,
)

CATALYST_TEMP = RangeThreshold(
    normal_low=300, normal_high=500,
    warning_low=200, warning_high=600,
    critical_low=100, critical_high=700,
)

STFT = AbsoluteThreshold(normal=5.0, warning=10.0, critical=15.0)
LTFT = AbsoluteThreshold(normal=5.0, warning=10.0, critical=15.0)


# --- Subsystem to PID mapping ---
# Which VehicleSnapshot fields feed into each subsystem's health score

SUBSYSTEM_PIDS: dict[str, list[str]] = {
    "engine":       ["rpm", "engine_load_pct", "throttle_pct", "maf_gps", "intake_manifold_kpa"],
    "transmission": ["cvt_fluid_temp_c"],
    "fuel":         ["stft_pct", "ltft_pct"],
    "cooling":      ["coolant_temp_c", "oil_temp_c"],
    "exhaust":      ["catalyst_temp_c"],
    "electrical":   ["battery_voltage"],
}

# How much each subsystem contributes to the overall score
SUBSYSTEM_WEIGHTS: dict[str, float] = {
    "engine":       0.30,
    "transmission": 0.20,
    "fuel":         0.15,
    "cooling":      0.15,
    "exhaust":      0.10,
    "electrical":   0.10,
}

# DTC severity penalties (applied to the relevant subsystem)
DTC_PENALTY_GENERIC = 15    # confirmed generic powertrain code
DTC_PENALTY_CRITICAL = 30   # misfire (P0300-P0304), catalyst (P0420), overtemp (P0217)
