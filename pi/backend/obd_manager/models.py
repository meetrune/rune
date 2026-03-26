"""Pydantic data models for Rune's vehicle data.

These models define the exact shape of every piece of data Rune reads.
They match confirmed supported PIDs on the 2026 Honda Accord SE (1.5T CVT).

Key decisions based on research:
- No fuel_rate_lph field -- PID 015E is NOT supported on Honda Accords.
  Fuel rate is calculated from MAF: (maf_gps / 14.7 / 750) * 3600
- No Bank 2 fuel trims -- single-bank 1.5T 4-cylinder engine
- cvt_fluid_temp_c is optional -- Mode 22 byte offset needs verification on 11th gen
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class VehicleSnapshot(BaseModel):
    """All sensor readings at one moment in time.

    Every field corresponds to a confirmed supported OBD-II PID
    on the Honda Accord, with ranges matching the PID formulas
    from ISO 15031-5.
    """

    timestamp: float = Field(default_factory=time.time)

    # PID 010C: (A*256+B)/4
    rpm: float = Field(ge=0, le=16383.75)

    # PID 010D: A (raw value in km/h)
    speed_kph: float = Field(ge=0, le=255)

    # PID 0105: A-40
    coolant_temp_c: float = Field(ge=-40, le=215)

    # PID 0104: A*100/255
    engine_load_pct: float = Field(ge=0, le=100)

    # PID 0111: A*100/255
    throttle_pct: float = Field(ge=0, le=100)

    # PID 010F: A-40
    intake_air_temp_c: float = Field(ge=-40, le=215)

    # PID 010B: A
    intake_manifold_kpa: float = Field(ge=0, le=255)

    # PID 0110: (A*256+B)/100 -- PRIMARY fuel calculation source
    maf_gps: float = Field(ge=0, le=655.35)

    # PID 0106: (A-128)*100/128 -- Bank 1 only (single-bank 4-cyl)
    stft_pct: float = Field(ge=-100, le=99.2)

    # PID 0107: (A-128)*100/128 -- Bank 1 only
    ltft_pct: float = Field(ge=-100, le=99.2)

    # PID 012F: A*100/255
    fuel_level_pct: float = Field(ge=0, le=100)

    # PID 013C: ((A*256+B)/10)-40
    catalyst_temp_c: float = Field(ge=-40, le=6513.5)

    # PID 015C: A-40
    oil_temp_c: float = Field(ge=-40, le=215)

    # PID 0142: (A*256+B)/1000
    battery_voltage: float = Field(ge=0, le=65.535)

    # Mode 22 PID 2201 byte 27: byte-40 (optional, needs 11th gen verification)
    cvt_fluid_temp_c: float | None = Field(default=None, ge=-40, le=215)

    # Pi-side sensors (Witty Pi 4 I2C + CPU thermal zone)
    vin_voltage: float | None = Field(default=None, ge=0, le=30)       # 12V rail input (Witty Pi ADC)
    armrest_temp_c: float | None = Field(default=None, ge=-55, le=125) # LM75B on Witty Pi board
    pi_cpu_temp_c: float | None = Field(default=None, ge=-40, le=120)  # BCM2711 junction temp
    pi_current_a: float | None = Field(default=None, ge=0, le=5)       # Pi current draw (Witty Pi shunt)


class HealthSnapshot(BaseModel):
    """Health scores for the vehicle and its subsystems.

    Each score is 0-100 where 100 = perfect health.
    Overall is a weighted combination of subsystems.
    """

    overall: float = Field(ge=-1, le=100)
    engine: float = Field(ge=-1, le=100)
    transmission: float = Field(ge=-1, le=100)
    fuel: float = Field(ge=-1, le=100)
    cooling: float = Field(ge=-1, le=100)
    exhaust: float = Field(ge=-1, le=100)
    electrical: float = Field(ge=-1, le=100)


class FuelSnapshot(BaseModel):
    """Fuel intelligence data calculated from sensor readings.

    instant_mpg is derived from MAF and speed, not a direct PID.
    """

    instant_mpg: float | None = Field(default=None, ge=0)
    idle_gph: float | None = Field(default=None, ge=0)  # gallons/hour when speed=0
    trip_fuel_gal: float = Field(default=0, ge=0)
    trip_cost_usd: float = Field(default=0, ge=0)
    trip_distance_mi: float = Field(default=0, ge=0)
    tank_pct: float = Field(ge=0, le=100)


class WebSocketMessage(BaseModel):
    """The full message sent to the phone at 10Hz.

    Matches the PRD Section 7 schema.
    """

    t: float = Field(default_factory=time.time)
    d: dict[str, dict[str, Any]] = Field(default_factory=dict)
    health: HealthSnapshot
    fuel: FuelSnapshot

    @staticmethod
    def from_snapshots(
        vehicle: VehicleSnapshot,
        health: HealthSnapshot,
        fuel: FuelSnapshot,
    ) -> WebSocketMessage:
        """Build a WebSocket message from component snapshots."""
        d: dict[str, dict[str, Any]] = {
            "RPM": {"v": round(vehicle.rpm, 1), "u": "rpm"},
            "SPEED": {"v": round(vehicle.speed_kph, 1), "u": "kph"},
            "COOLANT_TEMP": {"v": round(vehicle.coolant_temp_c, 1), "u": "degC"},
            "ENGINE_LOAD": {"v": round(vehicle.engine_load_pct, 1), "u": "pct"},
            "THROTTLE_POS": {"v": round(vehicle.throttle_pct, 1), "u": "pct"},
            "MAF": {"v": round(vehicle.maf_gps, 2), "u": "gps"},
            "FUEL_LEVEL": {"v": round(vehicle.fuel_level_pct, 1), "u": "pct"},
            "BATTERY_V": {"v": round(vehicle.battery_voltage, 2), "u": "V"},
            "STFT": {"v": round(vehicle.stft_pct, 1), "u": "pct"},
            "LTFT": {"v": round(vehicle.ltft_pct, 1), "u": "pct"},
            "INTAKE_TEMP": {"v": round(vehicle.intake_air_temp_c, 1), "u": "degC"},
            "MAP": {"v": round(vehicle.intake_manifold_kpa, 1), "u": "kPa"},
            "CATALYST_TEMP": {"v": round(vehicle.catalyst_temp_c, 1), "u": "degC"},
            "OIL_TEMP": {"v": round(vehicle.oil_temp_c, 1), "u": "degC"},
        }
        if vehicle.cvt_fluid_temp_c is not None:
            d["CVT_TEMP"] = {"v": round(vehicle.cvt_fluid_temp_c, 1), "u": "degC"}
        if vehicle.vin_voltage is not None:
            d["VIN_VOLTAGE"] = {"v": round(vehicle.vin_voltage, 2), "u": "V"}
        if vehicle.armrest_temp_c is not None:
            d["ARMREST_TEMP"] = {"v": round(vehicle.armrest_temp_c, 1), "u": "degC"}
        if vehicle.pi_cpu_temp_c is not None:
            d["PI_CPU_TEMP"] = {"v": round(vehicle.pi_cpu_temp_c, 1), "u": "degC"}
        if vehicle.pi_current_a is not None:
            d["PI_CURRENT"] = {"v": round(vehicle.pi_current_a, 2), "u": "A"}

        return WebSocketMessage(
            t=vehicle.timestamp,
            d=d,
            health=health,
            fuel=fuel,
        )


# --- Fuel calculation utility ---

# Constants for MAF-based fuel rate calculation
STOICHIOMETRIC_RATIO = 14.7  # air-to-fuel ratio for gasoline
GASOLINE_DENSITY_GPL = 750.0  # grams per liter
LITERS_PER_GALLON = 3.78541
KPH_TO_MPH = 0.621371


def maf_to_fuel_rate_lph(maf_gps: float) -> float:
    """Calculate fuel rate in liters/hour from MAF sensor reading.

    Formula: fuel_rate_lph = (MAF_gps / 14.7 / 750) * 3600
    This is the standard calculation used when PID 015E is unavailable,
    which is the case on all Honda Accords.
    """
    if maf_gps <= 0:
        return 0.0
    return (maf_gps / STOICHIOMETRIC_RATIO / GASOLINE_DENSITY_GPL) * 3600


def calculate_instant_mpg(speed_kph: float, maf_gps: float) -> float | None:
    """Calculate instant MPG from speed and MAF.

    Returns None when speed is 0 (use idle_gph instead).
    Capped at 199.9 MPG -- during deceleration/fuel-cutoff, very low MAF
    values can produce 600+ MPG which is physically meaningless and would
    overflow the hero display.
    """
    fuel_rate_lph = maf_to_fuel_rate_lph(maf_gps)
    if fuel_rate_lph <= 0:
        return None

    speed_mph = speed_kph * KPH_TO_MPH
    if speed_mph <= 0:
        return None

    fuel_rate_gph = fuel_rate_lph / LITERS_PER_GALLON
    mpg = speed_mph / fuel_rate_gph
    return min(mpg, 199.9)


def calculate_idle_gph(maf_gps: float) -> float:
    """Calculate fuel consumption in gallons/hour during idle."""
    fuel_rate_lph = maf_to_fuel_rate_lph(maf_gps)
    return fuel_rate_lph / LITERS_PER_GALLON
