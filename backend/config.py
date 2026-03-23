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

    # OBD-II connection
    obd_port: str = "/dev/ttyUSB0"
    obd_baudrate: int = 500000
    obd_protocol: str = "6"  # ISO 15765-4, 11-bit, 500 kbaud
    obd_fast: bool = True

    # WebSocket
    ws_rate_hz: int = 10

    # Vehicle (2026 Honda Accord SE)
    fuel_tank_capacity_gal: float = 14.8
    epa_combined_mpg: float = 31.0
    gas_price_per_gallon: float = 3.50  # USD, update weekly

    # Database
    db_path: str = "rune.db"

    # Modes
    use_simulator: bool = True  # True for desktop dev, False on Pi with real OBD
    log_level: str = "INFO"


# Singleton instance -- import this throughout the app
settings = RuneSettings()
