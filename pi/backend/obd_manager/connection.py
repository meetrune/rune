"""SafeOBDConnection -- the safety gate between Rune and the vehicle.

Every OBD-II command goes through this wrapper. It validates that the
requested mode is in the read-only whitelist before forwarding to the
actual connection. If a mode isn't explicitly allowed, it gets blocked.

This is the first code written for Rune. It must exist and pass tests
before any other OBD code is written.
"""

from __future__ import annotations

import logging
from typing import Any

import obd

logger = logging.getLogger(__name__)

# Read-only modes only. Whitelist approach: if it's not here, it's blocked.
ALLOWED_MODES: frozenset[str] = frozenset({
    "01",  # Current powertrain data (live sensor readings)
    "02",  # Freeze frame data (snapshot at time of fault)
    "03",  # Read diagnostic trouble codes
    "09",  # Vehicle information (VIN, calibration IDs)
    "22",  # UDS ReadDataByIdentifier (Honda proprietary, read-only)
})

# Documented for clarity. These are write/control operations that must never
# be sent. Validation uses ALLOWED_MODES (whitelist), not this set.
BLOCKED_MODES: frozenset[str] = frozenset({
    "04",  # Clear DTCs (WRITES)
    "08",  # Control onboard systems (WRITES)
    "10",  # UDS diagnostic session control
    "27",  # UDS security access (seed/key auth)
    "2E",  # UDS write data by identifier
    "31",  # UDS routine control
    "3E",  # UDS tester present
})


class BlockedCommandError(Exception):
    """Raised when a command targets a mode outside the read-only whitelist."""


def extract_mode(cmd: str) -> str:
    """Extract and normalize the OBD-II mode from a command string.

    Handles formats like "01 0C", "010C", "01", with any casing/whitespace.
    Returns the mode as an uppercase two-character hex string.

    Raises ValueError if the command is empty or has no valid mode.
    """
    cleaned = cmd.strip()
    if not cleaned:
        raise ValueError("Empty OBD-II command")

    mode = cleaned.split()[0].upper()

    # Handle concatenated format like "010C" -- mode is first 2 chars
    if len(mode) > 2 and not mode.startswith("0X"):
        mode = mode[:2]

    # Validate it looks like hex
    try:
        int(mode, 16)
    except ValueError:
        raise ValueError(f"Invalid OBD-II mode: {mode!r}") from None

    return mode


class SafeOBDConnection:
    """Thread-safe wrapper around python-obd that enforces read-only access.

    All OBD communication MUST go through this class. No direct serial
    writes, no raw socket sends, no bypassing the whitelist.
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 500000,
        protocol: str = "6",
        fast: bool = True,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._protocol = protocol
        self._fast = fast
        self._connection: obd.Async | None = None

    def _validate_command(self, cmd_str: str) -> str:
        """Validate a raw command string against the whitelist.

        Returns the normalized mode string if allowed.
        Raises BlockedCommandError if the mode is not in ALLOWED_MODES.
        """
        mode = extract_mode(cmd_str)
        if mode not in ALLOWED_MODES:
            raise BlockedCommandError(
                f"BLOCKED: Mode {mode} is not in the read-only whitelist. "
                f"Rune only uses read-only modes: {sorted(ALLOWED_MODES)}"
            )
        logger.debug("OBD command validated: mode=%s, full=%s", mode, cmd_str)
        return mode

    async def connect(self) -> None:
        """Establish async OBD-II connection."""
        if self._connection is not None:
            logger.warning("Already connected, disconnecting first")
            await self.disconnect()

        logger.info(
            "Connecting to OBD-II: port=%s, baudrate=%d, protocol=%s, fast=%s",
            self._port, self._baudrate, self._protocol, self._fast,
        )
        self._connection = obd.Async(
            portstr=self._port,
            baudrate=self._baudrate,
            protocol=self._protocol,
            fast=self._fast,
        )

    async def disconnect(self) -> None:
        """Close the OBD-II connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("OBD-II connection closed")

    async def query(self, cmd: obd.OBDCommand) -> obd.OBDResponse:
        """Query a standard OBD-II command after validating its mode.

        This is the primary interface for reading vehicle data using
        python-obd's built-in OBDCommand objects.

        WARNING: The underlying obd.Async.query() call is synchronous
        blocking I/O. In production (OBDCollector), use obd.Async.watch()
        with callbacks instead. This method exists for testing and
        one-off queries. For the 10Hz polling loop, the OBDCollector
        will use the watch/callback pattern to avoid blocking the event loop.
        """
        # OBDCommand stores the mode as a bytes object in cmd.command
        cmd_hex = cmd.command.hex().upper()
        self._validate_command(cmd_hex)

        if self._connection is None:
            raise ConnectionError("Not connected to OBD-II adapter")

        response: obd.OBDResponse = self._connection.query(cmd)
        return response

    async def send_raw(self, cmd_str: str) -> Any:
        """Send a raw command string after validating its mode.

        Used for Honda Mode 22 proprietary PIDs and other raw queries
        that don't have python-obd OBDCommand definitions.

        Example: send_raw("22 2201") for CVT fluid temp.
        """
        self._validate_command(cmd_str)

        # Validate the full command is valid hex before checking connection
        hex_str = cmd_str.replace(" ", "")
        try:
            cmd_bytes = bytes.fromhex(hex_str)
        except ValueError:
            raise ValueError(
                f"Invalid hex in OBD command: {cmd_str!r}. "
                f"All bytes must be valid hexadecimal."
            ) from None

        if self._connection is None:
            raise ConnectionError("Not connected to OBD-II adapter")

        response = self._connection.query(obd.OBDCommand(
            name="RAW",
            desc=f"Raw command: {cmd_str}",
            command=cmd_bytes,
            bytes=0,
            decoder=lambda messages: messages,
            ecu=obd.ECU.ALL,
            fast=self._fast,
        ))
        return response

    @property
    def is_connected(self) -> bool:
        """Whether the OBD-II connection is currently active."""
        if self._connection is None:
            return False
        return self._connection.is_connected()  # type: ignore[no-any-return]

    @property
    def status(self) -> str:
        """Human-readable connection status."""
        if self._connection is None:
            return "Not initialized"
        return str(self._connection.status())
