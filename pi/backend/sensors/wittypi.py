"""Witty Pi 4 sensor reader via I2C.

Reads input voltage (Vin), output voltage (Vout), output current (Iout),
and armrest temperature (LM75B) from the Witty Pi 4 MCU at I2C address 0x08.
Also reads Pi CPU temperature from the kernel thermal zone.

Register map verified against Witty Pi 4 firmware source:
  https://github.com/uugear/Witty-Pi-4/blob/main/Firmware/WittyPi4/WittyPi4.ino

All values are read-only. No writes to the Witty Pi MCU.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Witty Pi 4 I2C address (ATtiny841 MCU)
WITTYPI_I2C_ADDR = 0x08
I2C_BUS = 1

# Register addresses (from firmware source)
REG_VIN_INT = 0x01      # Input voltage, integer part (uint8, volts)
REG_VIN_DEC = 0x02      # Input voltage, decimal part (uint8, 0-99 hundredths)
REG_VOUT_INT = 0x03     # Output voltage, integer part
REG_VOUT_DEC = 0x04     # Output voltage, decimal part
REG_IOUT_INT = 0x05     # Output current, integer part (amps)
REG_IOUT_DEC = 0x06     # Output current, decimal part
REG_POWER_MODE = 0x07   # 1 = DC input, 0 = USB 5V
REG_LV_SHUTDOWN = 0x08  # 1 = last shutdown was low-voltage
REG_ACTION_REASON = 0x0B  # Why Pi woke up (see ACTION_REASONS)
REG_FW_REVISION = 0x0C  # Firmware revision
REG_LM75B_TEMP = 0x32   # Virtual register 50 (0x32): LM75B temperature, 2 bytes

# Action reasons (register 11)
ACTION_REASONS = {
    1: "alarm1",
    2: "alarm2",
    3: "button_click",
    4: "low_voltage",
    5: "voltage_restore",
    6: "over_temperature",
    7: "below_temperature",
    10: "power_connected",
    11: "reboot",
}

# Pi CPU thermal zone path (Trixie / standard kernel)
PI_THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")

# Retry config for I2C reads
I2C_MAX_RETRIES = 3
I2C_RETRY_DELAY_S = 0.05  # 50ms between retries


@dataclass
class PiSensorSnapshot:
    """All Pi-side sensor readings at one moment."""
    timestamp: float = field(default_factory=time.time)
    # Witty Pi 4 readings
    vin_voltage: float | None = None       # 12V rail input voltage (6-30V range)
    vout_voltage: float | None = None      # 5V output to Pi
    iout_amps: float | None = None         # Current draw (amps)
    armrest_temp_c: float | None = None    # LM75B on Witty Pi board (0.125C res)
    power_mode: int | None = None          # 1=DC, 0=USB
    action_reason: str | None = None       # Why Pi last booted
    # Pi internal
    cpu_temp_c: float | None = None        # BCM2711 junction temperature


def _decode_voltage(int_reg: int, dec_reg: int) -> float:
    """Decode Witty Pi voltage from integer + decimal registers.

    Firmware uses getDecimalPart(): (value - floor(value)) * 100
    So decimal register is 0-99, representing hundredths.
    """
    return float(int_reg) + float(dec_reg) / 100.0


def _decode_lm75b_temp(msb: int, lsb: int) -> float:
    """Decode LM75B temperature from 2-byte register.

    LM75B format (NXP datasheet, Table 4):
      Byte 0 (MSB): signed int8, whole degrees Celsius
      Byte 1 (LSB): top 3 bits = fractional (0.5, 0.25, 0.125)

    Range: -55C to +125C, resolution 0.125C.
    """
    # MSB is signed 8-bit (two's complement)
    if msb > 127:
        temp_int = msb - 256
    else:
        temp_int = msb

    # LSB: only top 3 bits matter (bits 7, 6, 5)
    frac_bits = (lsb >> 5) & 0x07
    temp_frac = frac_bits * 0.125

    # For negative temps, fractional part is subtracted
    if temp_int < 0:
        return float(temp_int) - temp_frac
    return float(temp_int) + temp_frac


def read_cpu_temp() -> float | None:
    """Read Pi CPU temperature from kernel thermal zone.

    Returns temperature in Celsius, or None if unavailable.
    /sys/class/thermal/thermal_zone0/temp returns millidegrees.
    """
    try:
        raw = PI_THERMAL_ZONE.read_text().strip()
        return int(raw) / 1000.0
    except (OSError, ValueError) as exc:
        logger.debug("Failed to read CPU temp: %s", exc)
        return None


class WittyPiReader:
    """Reads Witty Pi 4 sensors via I2C with retry logic.

    Uses smbus2 for I2C communication. Falls back gracefully
    if smbus2 is unavailable (Mac dev) or the Witty Pi is not
    connected (returns None for all readings).

    I2C bus contention: The Witty Pi daemon also reads I2C.
    smbus2 uses kernel-level I2C locking (ioctl), so concurrent
    reads are safe -- they serialize at the kernel level.
    """

    def __init__(self) -> None:
        self._bus: Any = None  # smbus2.SMBus (optional import)
        self._available = False
        self._last_error_log: float = 0.0

    async def start(self) -> None:
        """Initialize I2C bus connection."""
        try:
            import smbus2
            self._bus = smbus2.SMBus(I2C_BUS)
            # Verify Witty Pi is present by reading the ID register (reg 0)
            chip_id = self._read_byte(0x00)
            if chip_id == 0x26:
                self._available = True
                fw_rev = self._read_byte(REG_FW_REVISION)
                logger.info(
                    "Witty Pi 4 detected at 0x%02X, firmware rev %d",
                    WITTYPI_I2C_ADDR, fw_rev or 0,
                )
            else:
                logger.warning(
                    "I2C device at 0x%02X returned unexpected ID: 0x%02X",
                    WITTYPI_I2C_ADDR, chip_id or 0,
                )
                self._available = False
        except ImportError:
            logger.info("smbus2 not installed -- Witty Pi readings disabled (dev mode)")
            self._available = False
        except OSError as exc:
            logger.warning("I2C bus %d not available: %s", I2C_BUS, exc)
            self._available = False

    async def stop(self) -> None:
        """Close I2C bus."""
        if self._bus is not None:
            try:
                self._bus.close()
            except OSError:
                pass
            self._bus = None
            self._available = False
            logger.info("Witty Pi reader stopped")

    @property
    def is_available(self) -> bool:
        return self._available

    def _read_byte(self, register: int) -> int | None:
        """Read a single byte from a Witty Pi register with retries."""
        if self._bus is None:
            return None

        for attempt in range(I2C_MAX_RETRIES):
            try:
                return int(self._bus.read_byte_data(WITTYPI_I2C_ADDR, register))
            except OSError:
                if attempt < I2C_MAX_RETRIES - 1:
                    time.sleep(I2C_RETRY_DELAY_S)
                    continue
                self._log_error_throttled(
                    "I2C read failed for register 0x%02X after %d retries",
                    register, I2C_MAX_RETRIES,
                )
        return None

    def _read_two_bytes(self, register: int) -> tuple[int, int] | None:
        """Read two consecutive bytes from a Witty Pi register."""
        if self._bus is None:
            return None

        for attempt in range(I2C_MAX_RETRIES):
            try:
                data = self._bus.read_i2c_block_data(
                    WITTYPI_I2C_ADDR, register, 2,
                )
                return (int(data[0]), int(data[1]))
            except OSError:
                if attempt < I2C_MAX_RETRIES - 1:
                    time.sleep(I2C_RETRY_DELAY_S)
                    continue
                self._log_error_throttled(
                    "I2C block read failed for register 0x%02X after %d retries",
                    register, I2C_MAX_RETRIES,
                )
        return None

    def _log_error_throttled(self, msg: str, *args: object) -> None:
        """Log errors at most once every 30 seconds to avoid log spam."""
        now = time.time()
        if now - self._last_error_log > 30.0:
            logger.warning(msg, *args)
            self._last_error_log = now

    def read_snapshot(self) -> PiSensorSnapshot:
        """Read all Witty Pi sensors + CPU temp in one call.

        Returns a PiSensorSnapshot with None for any values that
        couldn't be read. Never raises -- always returns partial data.
        """
        snap = PiSensorSnapshot()

        # CPU temp is always available (even on Mac it returns None gracefully)
        snap.cpu_temp_c = read_cpu_temp()

        if not self._available:
            return snap

        # Vin (12V rail from car)
        vin_int = self._read_byte(REG_VIN_INT)
        vin_dec = self._read_byte(REG_VIN_DEC)
        if vin_int is not None and vin_dec is not None:
            snap.vin_voltage = _decode_voltage(vin_int, vin_dec)

        # Vout (5V to Pi)
        vout_int = self._read_byte(REG_VOUT_INT)
        vout_dec = self._read_byte(REG_VOUT_DEC)
        if vout_int is not None and vout_dec is not None:
            snap.vout_voltage = _decode_voltage(vout_int, vout_dec)

        # Iout (current draw)
        iout_int = self._read_byte(REG_IOUT_INT)
        iout_dec = self._read_byte(REG_IOUT_DEC)
        if iout_int is not None and iout_dec is not None:
            snap.iout_amps = _decode_voltage(iout_int, iout_dec)  # same decode

        # Power mode
        snap.power_mode = self._read_byte(REG_POWER_MODE)

        # Action reason (why Pi booted)
        reason_code = self._read_byte(REG_ACTION_REASON)
        if reason_code is not None:
            snap.action_reason = ACTION_REASONS.get(reason_code, f"unknown_{reason_code}")

        # LM75B temperature (2 bytes at virtual register 50)
        temp_bytes = self._read_two_bytes(REG_LM75B_TEMP)
        if temp_bytes is not None:
            snap.armrest_temp_c = _decode_lm75b_temp(temp_bytes[0], temp_bytes[1])

        return snap


class SimulatedWittyPiReader:
    """Fake Witty Pi reader for desktop development.

    Simulates realistic sensor values for a car environment:
    - Vin tracks typical Honda ELD cycling (12.4-14.8V)
    - Temperature follows a warmup curve from ambient
    - CPU temp follows a realistic idle curve
    """

    def __init__(self, ambient_temp_c: float = 25.0) -> None:
        self._ambient = ambient_temp_c
        self._start_time = time.time()
        self._available = True

    async def start(self) -> None:
        self._start_time = time.time()
        logger.info("Simulated Witty Pi reader started (ambient=%.1fC)", self._ambient)

    async def stop(self) -> None:
        logger.info("Simulated Witty Pi reader stopped")

    @property
    def is_available(self) -> bool:
        return self._available

    def read_snapshot(self) -> PiSensorSnapshot:
        import math
        elapsed = time.time() - self._start_time

        # Vin: simulate Honda ELD cycling between low-output and high-output
        # Cycle period ~60s, between 12.8V and 14.4V
        eld_cycle = math.sin(elapsed / 60.0 * 2 * math.pi)
        vin = 13.6 + 0.8 * eld_cycle  # 12.8 -- 14.4V

        # Armrest temp: starts at ambient, warms from Pi heat dissipation
        # Approaches ambient + 18C over ~30 minutes (tau = 600s)
        pi_heat_delta = 18.0 * (1 - math.exp(-elapsed / 600.0))
        armrest = self._ambient + pi_heat_delta

        # CPU temp: starts at armrest temp + 35C delta, warms with load
        cpu_base = armrest + 35.0
        cpu_load_delta = 5.0 * (1 - math.exp(-elapsed / 300.0))
        cpu_temp = cpu_base + cpu_load_delta

        return PiSensorSnapshot(
            vin_voltage=round(vin, 2),
            vout_voltage=round(5.05 + 0.05 * eld_cycle, 2),
            iout_amps=round(0.7 + 0.15 * math.sin(elapsed / 10.0), 2),
            armrest_temp_c=round(armrest, 1),
            power_mode=1,
            action_reason="power_connected",
            cpu_temp_c=round(cpu_temp, 1),
        )
