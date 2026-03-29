"""Rune configuration via Pydantic Settings.

Config hierarchy: defaults -> environment variables (RUNE_ prefix).
Vehicle profile YAML and user overrides come later.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class RuneSettings(BaseSettings):
    """Central configuration for Rune."""

    model_config = {"env_prefix": "RUNE_"}

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    # OBD-II connection -- WiCAN Pro ELM327 TCP on the Rune WiFi network
    obd_fast: bool = True

    # WiCAN Pro TCP connection
    wican_host: str = "192.168.4.100"
    wican_port: int = 3333
    obd_cmd_timeout: float = 2.0  # seconds per PID query
    obd_reconnect_max_backoff: float = 30.0  # max seconds between reconnect attempts
    obd_circuit_breaker_threshold: int = 5  # consecutive failures before disconnect
    obd_circuit_breaker_cooldown: float = 10.0  # seconds to wait after circuit break
    obd_stale_threshold: float = 5.0  # seconds before PID considered stale
    obd_mode22_enabled: bool = True  # attempt Mode 22 CVT temp query

    # WiCAN Pro raw CAN listener (port 35000 -- passive read-only)
    can_logging_enabled: bool = True  # log raw CAN frames alongside OBD PIDs
    wican_can_port: int = 35000  # raw CAN TCP port on WiCAN Pro

    # WebSocket
    ws_rate_hz: int = 10

    # Vehicle (2026 Honda Accord SE)
    fuel_tank_capacity_gal: float = 14.8
    epa_combined_mpg: float = 31.0
    gas_price_per_gallon: float = 3.50  # USD, update weekly

    # Database -- absolute path for Pi deployment; override with RUNE_DB_PATH env var for dev
    db_path: str = "/var/lib/rune/rune.db"

    # Modes
    use_simulator: bool = True  # True for desktop dev, False on Pi with real OBD
    log_level: str = "INFO"

    # Intelligence Layer
    intelligence_enabled: bool = True
    alert_rate_limit_seconds: float = 3600.0  # 1 alert per category per hour

    # DBC CAN decoding
    can_decode_enabled: bool = True  # decode raw CAN frames via DBC definitions

    # Battery monitoring -- thresholds from Interstate Battery State of Charge chart
    battery_resting_warn_v: float = 12.2   # 50% SOC
    battery_resting_critical_v: float = 12.0  # 25% SOC
    battery_charging_min_v: float = 13.5   # minimum healthy alternator output
    battery_ewma_alpha: float = 0.1        # smoothing factor for trend

    # Cold-start profiler
    coldstart_target_coolant_c: float = 80.0  # Honda thermostat opening temp
    coldstart_min_samples: int = 15           # samples needed before model fitting
    coldstart_anomaly_threshold: float = 1.3  # 30% deviation triggers alert

    # Trip scoring weights -- efficiency-heavy, aligned with telematics industry
    trip_score_efficiency_weight: float = 0.5
    trip_score_smoothness_weight: float = 0.3
    trip_score_idle_weight: float = 0.2
    trip_score_hard_accel_threshold: float = 15.0  # %/sec throttle rate-of-change
    trip_score_hard_brake_threshold: float = 11.3   # km/h per sec (~7 mph/sec, Progressive Snapshot)
    trip_score_baseline_alpha: float = 0.15         # EWMA for personal MPG baseline

    # Parked thermal guardian
    thermal_guardian_enabled: bool = True
    thermal_warm_c: float = 45.0     # start logging
    thermal_hot_c: float = 60.0      # queue alert, stay off
    thermal_extreme_c: float = 70.0  # critical alert, extend wake interval
    thermal_normal_wake_hours: float = 2.0
    thermal_extreme_wake_hours: float = 4.0

    # Maintenance intervals (miles) -- from 2026 Honda Accord SE owner's manual
    maint_oil_change_mi: float = 7500.0
    maint_oil_change_hot_mi: float = 5000.0  # if avg oil temp > 110C
    maint_air_filter_mi: float = 15000.0
    maint_cabin_filter_mi: float = 15000.0
    maint_cvt_fluid_mi: float = 30000.0
    maint_cvt_fluid_hot_mi: float = 25000.0  # if avg CVT temp > 90C
    maint_spark_plugs_mi: float = 60000.0
    maint_coolant_first_mi: float = 60000.0
    maint_coolant_subsequent_mi: float = 30000.0
    maint_brake_fluid_mi: float = 36000.0
    maint_tire_rotation_mi: float = 7500.0
    maint_alert_ahead_mi: float = 500.0  # alert this many miles before due


# Singleton instance -- import this throughout the app
settings = RuneSettings()
