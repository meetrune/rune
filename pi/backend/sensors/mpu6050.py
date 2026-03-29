"""MPU-6050 accelerometer/gyroscope reader via I2C (v3 -- sensor fusion).

Reads 3-axis acceleration and 3-axis angular velocity from the HiLetgo
GY-521 MPU-6050 breakout board at I2C address 0x68.

Wiring (Pi 4B GPIO header):
  VCC  -> Pin 1 (3.3V)
  GND  -> Pin 6 (GND)
  SCL  -> Pin 5 (GPIO 3, I2C1 SCL)
  SDA  -> Pin 3 (GPIO 2, I2C1 SDA)
  AD0  -> Not connected (address defaults to 0x68)

What this enables (v3):
  - Road surface quality detection (pothole counting, rough road segments)
  - Driving style analysis (hard braking, aggressive cornering, smooth acceleration)
  - Vibration pattern monitoring (engine mount health, wheel balance)
  - Complements OBD speed/RPM with physical motion data

MPU-6050 datasheet: InvenSense PS-MPU-6000A-00
Register map: RM-MPU-6000A-00
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# MPU-6050 I2C address (AD0 low = 0x68, AD0 high = 0x69)
MPU6050_I2C_ADDR = 0x68
I2C_BUS = 1

# Key registers
REG_WHO_AM_I = 0x75      # Should return 0x68
REG_PWR_MGMT_1 = 0x6B    # Power management (write 0x00 to wake up)
REG_ACCEL_XOUT_H = 0x3B  # Start of 14-byte burst read (accel + temp + gyro)

# Retry config
I2C_MAX_RETRIES = 3
I2C_RETRY_DELAY_S = 0.05


@dataclass
class MPU6050Reading:
    """Inertial measurement at one moment."""
    timestamp: float = field(default_factory=time.time)
    # Accelerometer (g-force, 1g = 9.81 m/s^2)
    accel_x_g: float | None = None    # Forward/backward
    accel_y_g: float | None = None    # Left/right
    accel_z_g: float | None = None    # Up/down (should be ~1g when flat)
    # Gyroscope (degrees per second)
    gyro_x_dps: float | None = None   # Roll rate
    gyro_y_dps: float | None = None   # Pitch rate
    gyro_z_dps: float | None = None   # Yaw rate
    # Die temperature (for self-calibration, not cabin temp)
    die_temp_c: float | None = None


class MPU6050Reader:
    """Reads MPU-6050 IMU via I2C with retry logic.

    Uses smbus2 for I2C communication. Falls back gracefully if smbus2
    is unavailable (Mac dev) or the sensor is not connected.

    NOT wired into the producer loop yet -- this is a v3 placeholder.
    """

    def __init__(self, addr: int = MPU6050_I2C_ADDR) -> None:
        self._bus: Any = None
        self._addr = addr
        self._available = False

    async def start(self) -> None:
        """Initialize I2C connection and wake up MPU-6050."""
        try:
            import smbus2  # type: ignore[import-untyped,unused-ignore]
            self._bus = smbus2.SMBus(I2C_BUS)
            # Verify WHO_AM_I register
            who = self._bus.read_byte_data(self._addr, REG_WHO_AM_I)
            if who == 0x68:
                # Wake up from sleep mode
                self._bus.write_byte_data(self._addr, REG_PWR_MGMT_1, 0x00)
                self._available = True
                logger.info("MPU-6050 connected at 0x%02X (WHO_AM_I=0x%02X)", self._addr, who)
            else:
                logger.warning("MPU-6050: unexpected WHO_AM_I 0x%02X at 0x%02X", who, self._addr)
        except Exception as exc:
            logger.info("MPU-6050 not available: %s (expected on Mac dev)", exc)

    async def stop(self) -> None:
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def read_snapshot(self) -> MPU6050Reading:
        """Read current acceleration and rotation.

        TODO (v3): Implement burst read of 14 bytes from REG_ACCEL_XOUT_H.
        Decode raw 16-bit signed values using sensitivity scale factors:
          Accel: +/- 2g default -> 16384 LSB/g
          Gyro:  +/- 250 dps default -> 131 LSB/dps
          Temp:  temp_c = raw / 340.0 + 36.53
        """
        if not self._available:
            return MPU6050Reading()
        # v3: actual I2C burst read + decode goes here
        return MPU6050Reading()


class SimulatedMPU6050Reader:
    """Mock MPU-6050 for desktop development."""

    async def start(self) -> None:
        logger.info("SimulatedMPU6050Reader started (motion simulation)")

    async def stop(self) -> None:
        pass

    def read_snapshot(self) -> MPU6050Reading:
        return MPU6050Reading(
            accel_x_g=0.02,     # Slight forward lean (normal driving)
            accel_y_g=0.01,     # Near-zero lateral
            accel_z_g=0.98,     # ~1g downward (gravity)
            gyro_x_dps=0.1,     # Minimal rotation
            gyro_y_dps=0.05,
            gyro_z_dps=0.02,
            die_temp_c=32.0,    # Sensor die temp (not cabin)
        )
