"""Rune CAN Decoder -- decode raw CAN frames into meaningful Honda signals.

Signal definitions sourced from comma.ai opendbc project (MIT license):
  https://github.com/commaai/opendbc/tree/master/opendbc/dbc/generator/honda

Files referenced:
  _honda_common.dbc -- WHEEL_SPEEDS, POWERTRAIN_DATA, ENGINE_DATA, CRUISE,
                        DOORS_STATUS, CAR_SPEED, KINEMATICS, VSA_STATUS
  _steering_sensors_a.dbc -- STEERING_SENSORS

These signals are confirmed on Honda Accord 10th gen CAN bus and shared
across multiple Honda models via the opendbc common DBC. The 2026 Accord
(11th gen) uses CAN-FD internally but the OBD-II port exposes standard CAN
at 500 kbaud. Signal byte layouts are the same on the standard CAN side.

NOTE: This is a lightweight purpose-built decoder, not a general DBC parser.
We decode only the specific signals Rune cares about, using hardcoded bit
definitions from the verified opendbc source. This avoids adding cantools
(heavy dependency) to the Pi.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DecodedSignal:
    """A single decoded CAN signal with its value and metadata."""
    signal_name: str
    value: float
    unit: str
    can_id: int
    message_name: str


def _extract_bits(data: bytes, start_bit: int, length: int, signed: bool = False) -> int:
    """Extract bits from CAN frame data using big-endian (Motorola) bit numbering.

    This matches the DBC convention used in opendbc Honda files where
    start_bit is the MSB position in big-endian bit numbering.

    The opendbc Honda DBC files use @0 (big-endian/Motorola) byte order
    for most signals. The bit numbering counts from MSB of byte 0.

    For a big-endian signal with start_bit=7, length=16:
      - This means MSB is at bit 7 (byte 0, bit 7)
      - The 16 bits span bytes 0 and 1: data[0]*256 + data[1]

    Args:
        data: Raw CAN frame bytes (8 bytes for standard CAN).
        start_bit: MSB bit position in Motorola/big-endian numbering.
        length: Number of bits in the signal.
        signed: Whether the value is signed (two's complement).

    Returns:
        Integer value extracted from the specified bit range.
    """
    # Convert Motorola start bit to byte position and bit offset
    start_byte = start_bit // 8
    start_bit_in_byte = start_bit % 8

    # For Motorola/big-endian signals, extract contiguously from MSB
    # Build the value by reading bits from MSB to LSB
    value = 0
    bits_remaining = length
    current_byte = start_byte
    current_bit = start_bit_in_byte

    while bits_remaining > 0:
        if current_byte >= len(data):
            # Signal extends past data boundary -- return what we have
            logger.debug(
                "CAN bit extraction truncated: start_bit=%d length=%d data_len=%d remaining=%d",
                start_bit, length, len(data), bits_remaining,
            )
            break
        # How many bits can we take from this byte (from current_bit down to 0)
        bits_in_byte = min(bits_remaining, current_bit + 1)
        # Extract those bits
        shift = current_bit - bits_in_byte + 1
        mask = ((1 << bits_in_byte) - 1) << shift
        extracted = (data[current_byte] & mask) >> shift
        value = (value << bits_in_byte) | extracted

        bits_remaining -= bits_in_byte
        current_byte += 1
        current_bit = 7  # Start from MSB of next byte

    if signed and value >= (1 << (length - 1)):
        value -= 1 << length

    return value


# --- Signal definition tables ---
# Each entry: (signal_name, start_bit, bit_length, scale, offset, unit, signed)
# Source: opendbc/dbc/generator/honda/_honda_common.dbc
# Bit numbering: Motorola/big-endian (@0 in DBC notation)

_WHEEL_SPEEDS_SIGNALS = [
    # CAN ID 0x1D0 (464) -- WHEEL_SPEEDS, DLC 8
    ("WHEEL_SPEED_FL", 7, 15, 0.01, 0.0, "kph", False),
    ("WHEEL_SPEED_FR", 8, 15, 0.01, 0.0, "kph", False),
    ("WHEEL_SPEED_RL", 25, 15, 0.01, 0.0, "kph", False),
    ("WHEEL_SPEED_RR", 42, 15, 0.01, 0.0, "kph", False),
]

_STEERING_SIGNALS = [
    # CAN ID 0x14A (330) -- STEERING_SENSORS, DLC 8
    # Source: opendbc/dbc/generator/honda/_steering_sensors_a.dbc
    ("STEER_ANGLE", 7, 16, -0.1, 0.0, "deg", True),
    ("STEER_ANGLE_RATE", 23, 16, -1.0, 0.0, "deg/s", True),
]

_POWERTRAIN_SIGNALS = [
    # CAN ID 0x17C (380) -- POWERTRAIN_DATA, DLC 8
    ("PEDAL_GAS", 7, 8, 1.0, 0.0, "", False),
    ("ENGINE_RPM", 23, 16, 1.0, 0.0, "rpm", False),
    ("GAS_PRESSED", 39, 1, 1.0, 0.0, "", False),
    ("BRAKE_PRESSED", 53, 1, 1.0, 0.0, "", False),
    ("BRAKE_SWITCH", 32, 1, 1.0, 0.0, "", False),
]

_ENGINE_DATA_SIGNALS = [
    # CAN ID 0x158 (344) -- ENGINE_DATA, DLC 8
    ("XMISSION_SPEED", 7, 16, 0.01, 0.0, "kph", False),
    ("ENGINE_RPM_ALT", 23, 16, 1.0, 0.0, "rpm", False),
    ("XMISSION_SPEED2", 39, 16, 0.01, 0.0, "kph", False),
]

_CRUISE_SIGNALS = [
    # CAN ID 0x324 (804) -- CRUISE, DLC 8
    ("HUD_SPEED_KPH", 7, 8, 1.0, 0.0, "kph", False),
    ("HUD_SPEED_MPH", 15, 8, 1.0, 0.0, "mph", False),
    ("TRIP_FUEL_CONSUMED", 23, 16, 1.0, 0.0, "", False),
    ("CRUISE_SPEED_PCM", 39, 8, 1.0, 0.0, "", False),
]

_DOORS_SIGNALS = [
    # CAN ID 0x405 (1029) -- DOORS_STATUS, DLC 8
    ("DOOR_OPEN_FL", 37, 1, 1.0, 0.0, "", False),
    ("DOOR_OPEN_FR", 38, 1, 1.0, 0.0, "", False),
    ("DOOR_OPEN_RL", 39, 1, 1.0, 0.0, "", False),
    ("DOOR_OPEN_RR", 40, 1, 1.0, 0.0, "", False),
    ("TRUNK_OPEN", 41, 1, 1.0, 0.0, "", False),
]

_CAR_SPEED_SIGNALS = [
    # CAN ID 0x309 (777) -- CAR_SPEED, DLC 8
    ("CAR_SPEED", 7, 16, 0.01, 0.0, "kph", False),
]

_KINEMATICS_SIGNALS = [
    # CAN ID 0x94 (148) -- KINEMATICS, DLC 8
    ("LAT_ACCEL", 7, 16, 0.0015, 0.0, "m/s2", True),
    ("LONG_ACCEL", 23, 16, 0.0015, 0.0, "m/s2", True),
]

_VSA_STATUS_SIGNALS = [
    # CAN ID 0x1A4 (420) -- VSA_STATUS, DLC 8
    ("USER_BRAKE", 7, 16, 0.015625, -1.609375, "", False),
]

# Master lookup: CAN ID -> (message_name, signal_definitions)
HONDA_SIGNAL_MAP: dict[int, tuple[str, list[tuple[str, int, int, float, float, str, bool]]]] = {
    0x1D0: ("WHEEL_SPEEDS", _WHEEL_SPEEDS_SIGNALS),
    0x14A: ("STEERING_SENSORS", _STEERING_SIGNALS),
    0x17C: ("POWERTRAIN_DATA", _POWERTRAIN_SIGNALS),
    0x158: ("ENGINE_DATA", _ENGINE_DATA_SIGNALS),
    0x324: ("CRUISE", _CRUISE_SIGNALS),
    0x405: ("DOORS_STATUS", _DOORS_SIGNALS),
    0x309: ("CAR_SPEED", _CAR_SPEED_SIGNALS),
    0x094: ("KINEMATICS", _KINEMATICS_SIGNALS),
    0x1A4: ("VSA_STATUS", _VSA_STATUS_SIGNALS),
}

# Set of CAN IDs we decode (for fast membership test in hot path)
DECODED_CAN_IDS: frozenset[int] = frozenset(HONDA_SIGNAL_MAP.keys())


class CANDecoder:
    """Decodes raw Honda CAN frames into named signals.

    Usage:
        decoder = CANDecoder()
        signals = decoder.decode_frame(can_id=0x1D0, data=frame_bytes)
        # signals = [DecodedSignal("WHEEL_SPEED_FL", 45.23, "kph", 0x1D0, "WHEEL_SPEEDS"), ...]

    Only decodes CAN IDs listed in HONDA_SIGNAL_MAP. Unknown IDs return [].
    """

    def __init__(self) -> None:
        self._decode_count = 0
        self._unknown_count = 0

    def decode_frame(self, can_id: int, data: bytes) -> list[DecodedSignal]:
        """Decode a single CAN frame into its component signals.

        Args:
            can_id: 11-bit CAN identifier (e.g., 0x1D0 for WHEEL_SPEEDS).
            data: Raw frame data bytes (typically 8 bytes for standard CAN).

        Returns:
            List of DecodedSignal objects. Empty list if CAN ID is unknown.
        """
        entry = HONDA_SIGNAL_MAP.get(can_id)
        if entry is None:
            return []

        message_name, signal_defs = entry
        signals: list[DecodedSignal] = []

        for sig_name, start_bit, bit_len, scale, offset, unit, signed in signal_defs:
            try:
                raw = _extract_bits(data, start_bit, bit_len, signed)
                value = raw * scale + offset
                signals.append(DecodedSignal(
                    signal_name=sig_name,
                    value=round(value, 4),
                    unit=unit,
                    can_id=can_id,
                    message_name=message_name,
                ))
            except (IndexError, struct.error):
                logger.debug(
                    "CAN decode error: id=0x%X signal=%s data_len=%d",
                    can_id, sig_name, len(data),
                )

        self._decode_count += 1
        return signals

    def decode_batch(
        self,
        frames: list[tuple[int, bytes]],
    ) -> list[DecodedSignal]:
        """Decode a batch of CAN frames.

        Args:
            frames: List of (can_id, data) tuples.

        Returns:
            Flat list of all decoded signals from all frames.
        """
        all_signals: list[DecodedSignal] = []
        for can_id, data in frames:
            if can_id in DECODED_CAN_IDS:
                all_signals.extend(self.decode_frame(can_id, data))
        return all_signals

    def get_stats(self) -> dict[str, int]:
        """Return decode statistics."""
        return {
            "decoded_frames": self._decode_count,
            "known_can_ids": len(HONDA_SIGNAL_MAP),
        }
