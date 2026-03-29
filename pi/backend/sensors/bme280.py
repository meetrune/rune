"""BME280 environmental sensor reader via I2C (v3 -- sensor fusion).

Reads cabin temperature, relative humidity, and atmospheric pressure
from the ZHWXFW BME280 breakout board at I2C address 0x76 (or 0x77).

Wiring (Pi 4B GPIO header):
  VIN  -> Pin 1 (3.3V)
  GND  -> Pin 6 (GND)
  SCL  -> Pin 5 (GPIO 3, I2C1 SCL)
  SDA  -> Pin 3 (GPIO 2, I2C1 SDA)

What this enables (v3):
  - Cabin temperature monitoring (complement to engine temps from OBD)
  - Humidity tracking (correlates with window fogging, HVAC load)
  - Barometric pressure (altitude estimation, weather-correlated MPG analysis)

BME280 datasheet: Bosch Sensortec BST-BME280-DS001
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# BME280 I2C address (SDO pin low = 0x76, SDO pin high = 0x77)
BME280_I2C_ADDR = 0x76
BME280_I2C_ADDR_ALT = 0x77
I2C_BUS = 1

# Retry config (same as wittypi.py pattern)
I2C_MAX_RETRIES = 3
I2C_RETRY_DELAY_S = 0.05


@dataclass
class BME280Reading:
    """Environmental sensor reading at one moment."""
    timestamp: float = field(default_factory=time.time)
    temp_c: float | None = None          # Cabin temperature (Celsius)
    humidity_pct: float | None = None    # Relative humidity (0-100%)
    pressure_hpa: float | None = None    # Atmospheric pressure (hPa / mbar)


class BME280Reader:
    """Reads BME280 environmental sensor via I2C with retry logic.

    Uses smbus2 for I2C communication. Falls back gracefully if smbus2
    is unavailable (Mac dev) or the sensor is not connected.

    NOT wired into the producer loop yet -- this is a v3 placeholder.
    """

    def __init__(self, addr: int = BME280_I2C_ADDR) -> None:
        self._bus: Any = None
        self._addr = addr
        self._available = False

    async def start(self) -> None:
        """Initialize I2C connection to BME280."""
        try:
            import smbus2  # type: ignore[import-untyped,unused-ignore]
            self._bus = smbus2.SMBus(I2C_BUS)
            # Read chip ID register (0xD0) -- BME280 should return 0x60
            chip_id = self._bus.read_byte_data(self._addr, 0xD0)
            if chip_id == 0x60:
                self._available = True
                logger.info("BME280 connected at 0x%02X (chip ID 0x%02X)", self._addr, chip_id)
            else:
                logger.warning("BME280: unexpected chip ID 0x%02X at 0x%02X", chip_id, self._addr)
        except Exception as exc:
            logger.info("BME280 not available: %s (expected on Mac dev)", exc)

    async def stop(self) -> None:
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def read_snapshot(self) -> BME280Reading:
        """Read current environmental conditions.

        TODO (v3): Implement full BME280 compensation algorithm
        (temperature, pressure, humidity from raw ADC values using
        calibration data from registers 0x88-0xA1 and 0xE1-0xE7).
        """
        if not self._available:
            return BME280Reading()
        # v3: actual I2C reads + compensation algorithm go here
        return BME280Reading()


class SimulatedBME280Reader:
    """Mock BME280 for desktop development."""

    async def start(self) -> None:
        logger.info("SimulatedBME280Reader started (cabin env simulation)")

    async def stop(self) -> None:
        pass

    def read_snapshot(self) -> BME280Reading:
        return BME280Reading(
            temp_c=23.5,         # Comfortable cabin temp
            humidity_pct=45.0,   # Normal indoor humidity
            pressure_hpa=1013.25,  # Standard atmosphere
        )
