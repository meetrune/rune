"""Pydantic models for the Rune Intelligence Layer.

All data structures used by intelligence features:
alert queue, sync engine, cold-start profiler, battery monitor,
trip scorer, thermal guardian, and maintenance tracker.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Alert Queue ---

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCategory(str, Enum):
    """Alert categories matching intelligence features."""
    FUEL_TRIM = "fuel_trim"
    BATTERY = "battery"
    THERMAL = "thermal"
    MAINTENANCE = "maintenance"
    COLD_START = "cold_start"
    ANOMALY = "anomaly"
    DTC = "dtc"
    SYSTEM = "system"


class Alert(BaseModel):
    """A queued alert waiting to be synced to iPhone."""
    id: int | None = None
    timestamp: float = Field(default_factory=time.time)
    severity: AlertSeverity
    category: AlertCategory
    message: str
    data: dict[str, Any] | None = None
    synced: bool = False
    synced_at: float | None = None


# --- Sync Engine ---

class SyncStatus(BaseModel):
    """Current sync state for the iPhone relay."""
    last_sync_at: float | None = None
    pending_alerts: int = 0
    readings_since_sync: int = 0
    data_size_bytes: int = 0


class DeltaExport(BaseModel):
    """Incremental data export since last sync."""
    since_ts: float
    until_ts: float
    readings_count: int
    trips: list[dict[str, Any]] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    checksum: str = ""


# --- Cold-Start Profiler ---

class ColdStartRecord(BaseModel):
    """A single cold-start warmup observation.

    Used to build the warmup model: warmup_min = f(ambient_temp).
    Physics basis: Newton's law of heating (exponential approach to
    thermostat equilibrium temperature).
    """
    trip_id: int | None = None
    ambient_temp_c: float
    start_coolant_c: float
    target_coolant_c: float = 80.0  # Honda thermostat opens at ~80-82C
    warmup_seconds: float
    timestamp: float = Field(default_factory=time.time)


class WarmupModel(BaseModel):
    """Fitted warmup curve parameters.

    Model: warmup_min = a * exp(-b * ambient_C) + c
    Fitted via scipy.optimize.curve_fit after 15+ cold starts.
    """
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    n_samples: int = 0
    r_squared: float = 0.0
    last_fit_at: float | None = None


# --- Battery Health ---

class BatteryState(str, Enum):
    """Battery state classification.

    Voltage thresholds from Interstate Battery State of Charge chart
    for standard lead-acid automotive batteries (12V SLI).
    Source: Interstate Battery technical documentation.
    """
    FULL = "full"           # >= 12.6V resting
    GOOD = "good"           # 12.4-12.6V resting
    FAIR = "fair"           # 12.2-12.4V resting
    LOW = "low"             # 12.0-12.2V resting
    CRITICAL = "critical"   # < 12.0V resting
    CHARGING = "charging"        # > 13.5V (engine running, healthy alternator)
    WEAK_CHARGING = "weak_charging"  # engine running but < 13.5V (alternator issue)
    UNKNOWN = "unknown"


class BatteryReading(BaseModel):
    """A battery voltage observation with context."""
    timestamp: float = Field(default_factory=time.time)
    voltage: float
    engine_running: bool
    minutes_since_trip_end: float | None = None
    state: BatteryState = BatteryState.UNKNOWN


class BatteryTrend(BaseModel):
    """Battery health trend over time."""
    resting_voltage_ewma: float = 12.6
    charging_voltage_ewma: float = 14.0
    drain_rate_v_per_hour: float = 0.0
    state: BatteryState = BatteryState.UNKNOWN
    samples: int = 0


# --- Trip Scoring ---

class TripScore(BaseModel):
    """Trip score with three axes.

    Scoring methodology informed by:
    - Efficiency: personal baseline comparison (standard practice)
    - Smoothness: throttle rate-of-change, hard braking detection
      Source: NHTSA eco-driving studies, Progressive Snapshot
      published threshold (7 mph/sec for hard braking)
    - Idle ratio: time at RPM>0 + speed=0 vs total
    - Composite weights: efficiency-heavy (0.5/0.3/0.2)
      Aligned with telematics industry practice.
    """
    efficiency: float = Field(ge=0, le=100)
    smoothness: float = Field(ge=0, le=100)
    idle_ratio: float = Field(ge=0, le=100)
    composite: float = Field(ge=0, le=100)
    trip_mpg: float = Field(ge=0)
    baseline_mpg: float = Field(ge=0)
    hard_accel_count: int = Field(ge=0, default=0)
    hard_brake_count: int = Field(ge=0, default=0)


# --- Thermal Guardian ---

class ParkedThermalState(str, Enum):
    """Parked thermal monitoring state."""
    NORMAL = "normal"       # < 45C, 2-hour wake cycle
    WARM = "warm"           # 45-60C, 2-hour wake cycle with logging
    HOT = "hot"             # 60-70C, alert queued, stay off
    EXTREME = "extreme"     # > 70C, 4-hour wake cycle, critical alert


class ParkedCheckResult(BaseModel):
    """Result of a parked thermal + battery check."""
    timestamp: float = Field(default_factory=time.time)
    armrest_temp_c: float | None = None
    cpu_temp_c: float | None = None
    vin_voltage: float | None = None
    thermal_state: ParkedThermalState = ParkedThermalState.NORMAL
    next_wake_hours: float = 2.0
    alerts_queued: int = 0


# --- Maintenance Tracker ---

class MaintenanceItem(str, Enum):
    """Tracked maintenance items for 2026 Honda Accord SE.

    Intervals from Honda owner's manual maintenance schedule.
    """
    OIL_CHANGE = "oil_change"
    AIR_FILTER = "air_filter"
    CABIN_FILTER = "cabin_filter"
    CVT_FLUID = "cvt_fluid"
    SPARK_PLUGS = "spark_plugs"
    COOLANT = "coolant"
    BRAKE_FLUID = "brake_fluid"
    TIRE_ROTATION = "tire_rotation"


class MaintenanceRecord(BaseModel):
    """A completed maintenance event."""
    id: int | None = None
    item: MaintenanceItem
    done_at: float = Field(default_factory=time.time)
    odometer_miles: float
    next_due_miles: float
    notes: str = ""


class MaintenanceStatus(BaseModel):
    """Current maintenance status for all tracked items."""
    item: MaintenanceItem
    last_done_miles: float | None = None
    last_done_at: float | None = None
    next_due_miles: float
    miles_remaining: float
    interval_miles: float
    adjusted: bool = False  # True if interval was reduced due to sensor data
    adjustment_reason: str = ""
