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


# Singleton instance -- import this throughout the app
settings = RuneSettings()
