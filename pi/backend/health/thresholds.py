"""Honda Accord 2026 SE (L15BE 1.5T) normal/warning/critical operating ranges.

Values sourced from Honda service manual data, forum scan tool logs, and
ISO 15031-5 PID specifications. Verified against real-world OBD-II captures
from 10th/11th gen Accord 1.5T owners.

Each parameter has three zones:
- Normal: 100 points, everything is fine
- Warning: 85 points, worth watching
- Critical: 50 points, needs attention soon

Important Honda-specific notes:
- Honda ELD (Electrical Load Detector) intentionally drops alternator output
  to 12.4-12.9V during low-load cruising to reduce fuel consumption. This is
  NORMAL behavior, not a charging system fault. The voltage thresholds here
  account for this by keeping the normal floor at 12.0V.
- Oil temp on L15BE is ECU-calculated (no physical oil temp sensor). Values
  come from PID 015C which returns the ECU's estimate.
- Catalyst runs cooler on the 1.5T than NA engines because the turbo has an
  integrated exhaust manifold that absorbs heat before the cat.
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


# --- Honda Accord 2026 SE (L15BE 1.5T) Operating Ranges ---

# Coolant temp: thermostat opens at ~82C, stabilizes 88-95C in normal driving.
# City driving in summer heat can push to 100-103C -- still within Honda spec.
# Warning starts at 100C. Critical at 108C (Honda fans go high-speed at ~107C).
# Low-side thresholds: during warmup, temps below normal_low are expected.
# warning_low acts as a "still warming up" floor.
# critical_low is the genuine concern level (sensor failure or extreme cold).
COOLANT_TEMP = RangeThreshold(
    normal_low=75, normal_high=100,
    warning_low=40, warning_high=105,
    critical_low=0, critical_high=110,
)

# Oil temp: ECU-calculated, not a physical sensor on L15BE.
# Normal operating range 80-120C. Long highway pulls or hot summer city
# driving can sustain 110-115C without issue.
OIL_TEMP = RangeThreshold(
    normal_low=80, normal_high=120,
    warning_low=40, warning_high=130,
    critical_low=0, critical_high=140,
)

# Idle RPM (Park/Neutral, engine warm): Honda targets 700 RPM.
# With AC compressor cycling, can sit 750-850. Below 550 or above 1000
# at warm idle indicates an issue.
IDLE_RPM = RangeThreshold(
    normal_low=700, normal_high=850,
    warning_low=550, warning_high=1000,
    critical_low=400, critical_high=1200,
)

# Battery voltage: Honda uses ELD to intentionally cycle alternator output.
# Normal driving sees 12.4-14.8V depending on ELD state. A sustained reading
# of 12.0V is the low end of acceptable. Below 11.8V or above 15.2V is a
# real charging issue.
BATTERY_VOLTAGE = RangeThreshold(
    normal_low=12.0, normal_high=15.0,
    warning_low=11.8, warning_high=15.2,
    critical_low=11.0, critical_high=16.0,
)

# Engine load at idle: 15-40% is normal. AC compressor adds ~10-15%.
# 25-40% with AC on is expected. Above 50% sustained at idle is unusual.
ENGINE_LOAD_IDLE = RangeThreshold(
    normal_low=15, normal_high=40,
    warning_low=10, warning_high=50,
    critical_low=5, critical_high=60,
)

# CVT fluid temp: Honda CVT fluid operates cooler than traditional ATF.
# Normal range 50-100C. Mountain towing or aggressive city driving can
# push 100-115C. Above 130C risks CVT belt/chain damage.
CVT_FLUID_TEMP = RangeThreshold(
    normal_low=50, normal_high=100,
    warning_low=20, warning_high=115,
    critical_low=0, critical_high=130,
)

# Catalyst temp: turbo integrated exhaust manifold absorbs heat before the
# cat, so the 1.5T runs cooler than NA engines. Normal operating range
# 300-800C. Sustained above 1000C indicates a problem (misfires, rich
# running dumping unburned fuel into the cat).
CATALYST_TEMP = RangeThreshold(
    normal_low=300, normal_high=800,
    warning_low=100, warning_high=950,
    critical_low=0, critical_high=1050,
)

# Short-term fuel trim: +/-10% is normal closed-loop correction.
# +/-10 to +/-15% means the ECU is working harder to compensate.
# Beyond +/-25% the ECU is near its correction limit.
STFT = AbsoluteThreshold(normal=10.0, warning=15.0, critical=25.0)

# Long-term fuel trim: +/-5% is well-adapted. +/-5 to +/-8% means slow
# drift (dirty air filter, slight vacuum leak). Beyond +/-10% sustained
# means the ECU is near its adaptation limit.
# Gap between warning and critical prevents score oscillation from noise.
LTFT = AbsoluteThreshold(normal=5.0, warning=8.0, critical=10.0)


# --- EWMA alpha values ---
# Empirically grounded based on sensor thermal mass and update characteristics.
# alpha = 2/(N+1) where N is the effective window in samples at 10Hz.
EWMA_ALPHAS: dict[str, float] = {
    "coolant_temp_c": 0.01,     # slow thermal mass, N~200, ~20s window
    "ltft_pct": 0.02,           # very slow ECU-averaged adaptation, N~100, ~10s
    "battery_voltage": 0.05,    # fast but ELD cycles, N~40, ~4s to smooth cycling
    "catalyst_temp_c": 0.02,    # moderate thermal mass, N~100, ~10s
    "oil_temp_c": 0.01,         # ECU-calculated, slow, N~200, ~20s
}


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
