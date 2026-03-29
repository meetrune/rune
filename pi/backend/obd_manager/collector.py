"""Data collector abstraction layer.

The rest of the app talks to a DataCollector, not directly to the
simulator or OBD connection. When the real hardware arrives, we swap
the source underneath and nothing else changes.

Think of it like a TV remote -- you press "get data" and it works
whether the source is the simulator or the real WiCAN Pro.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from backend.config import RuneSettings, settings
from backend.obd_manager.connection import SafeOBDConnection, BlockedCommandError
from backend.obd_manager.models import VehicleSnapshot
from backend.obd_manager.simulator import AnomalyConfig, HondaAccordSimulator

logger = logging.getLogger(__name__)


class DataCollector(ABC):
    """Abstract base for all data sources."""

    @abstractmethod
    async def start(self) -> None:
        """Start collecting data."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop collecting data."""

    @abstractmethod
    async def get_snapshot(self) -> VehicleSnapshot:
        """Get the current vehicle state."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Whether the collector is actively running."""


class SimulatedCollector(DataCollector):
    """Collector backed by the Honda Accord simulator.

    Used during development (Mac) and testing. Produces realistic
    sensor data without any hardware.
    """

    def __init__(
        self,
        ambient_temp_c: float = 20.0,
        initial_fuel_pct: float = 75.0,
        anomalies: list[AnomalyConfig] | None = None,
    ) -> None:
        self._sim = HondaAccordSimulator(
            ambient_temp_c=ambient_temp_c,
            initial_fuel_pct=initial_fuel_pct,
            anomalies=anomalies,
        )

    async def start(self) -> None:
        self._sim.start()
        logger.info("SimulatedCollector started")

    async def stop(self) -> None:
        self._sim.stop()
        logger.info("SimulatedCollector stopped")

    async def get_snapshot(self) -> VehicleSnapshot:
        return self._sim.get_snapshot()

    @property
    def is_running(self) -> bool:
        return self._sim.is_running


# --- PID definitions for ELM327 Mode 01 polling ---

@dataclass(frozen=True)
class PIDDef:
    """Definition of an OBD-II PID: command string, field name, decoder."""
    cmd: str          # ELM327 command to send (e.g. "010C")
    field: str        # VehicleSnapshot field name
    data_bytes: int   # expected data byte count


# All 14 Mode 01 PIDs confirmed supported on 2026 Honda Accord SE
PID_TABLE: tuple[PIDDef, ...] = (
    PIDDef(cmd="010C", field="rpm", data_bytes=2),
    PIDDef(cmd="010D", field="speed_kph", data_bytes=1),
    PIDDef(cmd="0105", field="coolant_temp_c", data_bytes=1),
    PIDDef(cmd="0104", field="engine_load_pct", data_bytes=1),
    PIDDef(cmd="0111", field="throttle_pct", data_bytes=1),
    PIDDef(cmd="010F", field="intake_air_temp_c", data_bytes=1),
    PIDDef(cmd="010B", field="intake_manifold_kpa", data_bytes=1),
    PIDDef(cmd="0110", field="maf_gps", data_bytes=2),
    PIDDef(cmd="0106", field="stft_pct", data_bytes=1),
    PIDDef(cmd="0107", field="ltft_pct", data_bytes=1),
    PIDDef(cmd="012F", field="fuel_level_pct", data_bytes=1),
    PIDDef(cmd="013C", field="catalyst_temp_c", data_bytes=2),
    PIDDef(cmd="0142", field="battery_voltage", data_bytes=2),
    PIDDef(cmd="015C", field="oil_temp_c", data_bytes=1),
)


def decode_pid(pid_def: PIDDef, data_bytes: list[int]) -> float:
    """Decode raw data bytes into a physical value using standard OBD-II formulas.

    Formulas from ISO 15031-5 / SAE J1979, matching the comments in models.py.
    """
    a = data_bytes[0] if len(data_bytes) > 0 else 0
    b = data_bytes[1] if len(data_bytes) > 1 else 0

    match pid_def.field:
        case "rpm":
            return (a * 256 + b) / 4.0
        case "speed_kph":
            return float(a)
        case "coolant_temp_c" | "intake_air_temp_c" | "oil_temp_c":
            return float(a - 40)
        case "engine_load_pct" | "throttle_pct" | "fuel_level_pct":
            return a * 100.0 / 255.0
        case "intake_manifold_kpa":
            return float(a)
        case "maf_gps":
            return (a * 256 + b) / 100.0
        case "stft_pct" | "ltft_pct":
            return (a - 128) * 100.0 / 128.0
        case "catalyst_temp_c":
            return (a * 256 + b) / 10.0 - 40.0
        case "battery_voltage":
            return (a * 256 + b) / 1000.0
        case _:
            logger.warning("Unknown PID field: %s", pid_def.field)
            return 0.0


def parse_elm_response(raw: str, pid_def: PIDDef) -> float | None:
    """Parse an ELM327 hex response string into a decoded value.

    Expected format (spaces off): "410C0FA0" where:
    - First byte (41) = mode + 0x40
    - Second byte (0C) = PID
    - Remaining bytes = data

    Returns None if the response indicates an error or unsupported PID.
    """
    cleaned = raw.strip().replace(" ", "").replace("\r", "").replace("\n", "")

    # Error responses from ELM327
    if not cleaned or "NODATA" in cleaned.upper() or "ERROR" in cleaned.upper():
        return None
    if "UNABLETOCONNECT" in cleaned.upper():
        return None
    if cleaned.upper().startswith("7F"):
        # Negative response from ECU
        return None

    # Strip any non-hex characters (sometimes ELM adds garbage)
    hex_chars = ""
    for ch in cleaned:
        if ch in "0123456789ABCDEFabcdef":
            hex_chars += ch
        else:
            break  # stop at first non-hex (like '>')

    if len(hex_chars) < 4:
        logger.warning("Response too short: %r", raw)
        return None

    try:
        response_bytes = [int(hex_chars[i:i+2], 16) for i in range(0, len(hex_chars), 2)]
    except ValueError:
        logger.warning("Failed to parse hex from response: %r", raw)
        return None

    # Validate mode echo (mode + 0x40)
    expected_cmd = pid_def.cmd.upper()
    expected_mode = int(expected_cmd[:2], 16) + 0x40
    expected_pid = int(expected_cmd[2:4], 16)

    if response_bytes[0] != expected_mode or response_bytes[1] != expected_pid:
        logger.warning(
            "Response header mismatch: expected %02X%02X, got %02X%02X",
            expected_mode, expected_pid, response_bytes[0], response_bytes[1],
        )
        return None

    data = response_bytes[2:]
    if len(data) < pid_def.data_bytes:
        logger.warning(
            "Not enough data bytes for %s: expected %d, got %d",
            pid_def.field, pid_def.data_bytes, len(data),
        )
        return None

    return decode_pid(pid_def, data)


def parse_mode22_cvt_response(raw: str) -> float | None:
    """Parse Mode 22 response for CVT fluid temperature.

    Command: 222201
    Response: 622201... (byte 27 from data start = temp, byte - 40 = Celsius)
    Returns None on error or negative UDS response.
    """
    cleaned = raw.strip().replace(" ", "").replace("\r", "").replace("\n", "")

    if not cleaned or "NODATA" in cleaned.upper() or "ERROR" in cleaned.upper():
        return None
    if cleaned.upper().startswith("7F"):
        return None

    hex_chars = ""
    for ch in cleaned:
        if ch in "0123456789ABCDEFabcdef":
            hex_chars += ch
        else:
            break

    try:
        response_bytes = [int(hex_chars[i:i+2], 16) for i in range(0, len(hex_chars), 2)]
    except ValueError:
        return None

    # Response should start with 62 22 01 (positive response to 22 2201)
    if len(response_bytes) < 3:
        return None
    if response_bytes[0] != 0x62 or response_bytes[1] != 0x22 or response_bytes[2] != 0x01:
        return None

    # Byte 27 from the data start (after the 3-byte header)
    # So overall index = 3 + 27 = 30
    data_offset = 27
    total_index = 3 + data_offset
    if len(response_bytes) <= total_index:
        logger.warning(
            "Mode 22 response too short for CVT temp: %d bytes, need %d",
            len(response_bytes), total_index + 1,
        )
        return None

    return float(response_bytes[total_index] - 40)


# --- ELM327 init sequence ---

AT_INIT_SEQUENCE: tuple[tuple[str, str | None], ...] = (
    ("ATZ\r", "ELM"),        # Reset, expect "ELM327" or "STN" in response
    ("ATE0\r", "OK"),        # Echo off
    ("ATL0\r", "OK"),        # Linefeeds off
    ("ATS0\r", "OK"),        # Spaces off (faster parsing)
    ("ATSP6\r", "OK"),       # Protocol: ISO 15765-4, 11-bit, 500kbaud (MANDATORY)
    ("ATSH7E0\r", "OK"),     # Set header to ECU request address
    ("ATCRA7E8\r", "OK"),    # Filter responses to ECU only
)


@dataclass
class _PIDState:
    """Tracks the latest value and freshness of a single PID."""
    value: float = 0.0
    last_updated: float = field(default_factory=time.time)
    stale_logged: bool = False


class OBDCollector(DataCollector):
    """Collector backed by a real OBD-II connection to WiCAN Pro via TCP.

    Connects to the WiCAN Pro adapter in ELM327 emulation mode over a
    plain TCP socket. Sends AT init commands, then continuously polls
    Mode 01 PIDs and (optionally) Mode 22 for CVT fluid temp.

    All commands are validated through SafeOBDConnection._validate_command()
    to enforce the read-only whitelist before any bytes hit the wire.
    """

    def __init__(self, config: RuneSettings | None = None) -> None:
        self._config = config or settings
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._running = False
        self._poll_task: asyncio.Task[None] | None = None

        # Safety gate -- we use _validate_command() from this, not the full connection
        self._validator = SafeOBDConnection()

        # PID state: field_name -> _PIDState
        self._pid_state: dict[str, _PIDState] = {
            pid.field: _PIDState() for pid in PID_TABLE
        }
        self._cvt_temp: float | None = None
        self._cvt_last_updated: float = 0.0

        # Circuit breaker state
        self._consecutive_failures = 0
        self._reconnect_failures = 0
        self._mode22_disabled = False

        # Backoff for reconnects
        self._backoff_seconds = 1.0

    async def start(self) -> None:
        """Start the polling loop. Connects to WiCAN Pro if available.

        If the adapter isn't ready (car off, adapter booting), the server
        still starts. The poll loop will retry connection with backoff.
        """
        if self._running:
            logger.warning("OBDCollector already running")
            return

        try:
            await self._connect()
        except ConnectionError:
            logger.warning(
                "WiCAN Pro not reachable at %s:%d -- will retry in poll loop",
                self._config.wican_host, self._config.wican_port,
            )

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(
            "OBDCollector started, polling %d PIDs from %s:%d",
            len(PID_TABLE), self._config.wican_host, self._config.wican_port,
        )

    async def stop(self) -> None:
        """Stop polling and close the TCP connection."""
        self._running = False
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        await self._disconnect()
        logger.info("OBDCollector stopped")

    async def get_snapshot(self) -> VehicleSnapshot:
        """Build a VehicleSnapshot from the latest polled PID values.

        Returns the most recent data for each PID, even if some are stale.
        Stale PIDs are logged as warnings but still included -- partial
        data is better than no data.
        """
        now = time.time()
        stale_threshold = self._config.obd_stale_threshold

        values: dict[str, float] = {}
        for field_name, state in self._pid_state.items():
            age = now - state.last_updated
            if age > stale_threshold and not state.stale_logged:
                logger.warning(
                    "PID %s is stale (%.1fs since last update)", field_name, age,
                )
                state.stale_logged = True
            elif age <= stale_threshold:
                state.stale_logged = False
            values[field_name] = state.value

        return VehicleSnapshot(
            timestamp=now,
            cvt_fluid_temp_c=self._cvt_temp,
            **values,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    # --- TCP connection management ---

    async def _connect(self) -> None:
        """Open TCP connection and run the ELM327 init sequence."""
        host = self._config.wican_host
        port = self._config.wican_port
        timeout = self._config.obd_cmd_timeout

        logger.info("Connecting to WiCAN Pro at %s:%d", host, port)

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout * 2,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            logger.error("TCP connection failed to %s:%d: %s", host, port, exc)
            raise ConnectionError(
                f"Failed to connect to WiCAN Pro at {host}:{port}"
            ) from exc

        # Run ELM327 init sequence
        await self._run_init_sequence()

        # Reset circuit breaker on successful connect
        self._consecutive_failures = 0
        self._reconnect_failures = 0
        self._backoff_seconds = 1.0
        logger.info("WiCAN Pro connection established and initialized")

    async def _disconnect(self) -> None:
        """Close the TCP connection."""
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass  # already closed
            self._writer = None
            self._reader = None
            logger.info("TCP connection closed")

    async def _reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff.

        Returns True on success, False on failure.
        """
        await self._disconnect()

        logger.info(
            "Reconnecting in %.1fs (attempt backoff)", self._backoff_seconds,
        )
        await asyncio.sleep(self._backoff_seconds)

        try:
            await self._connect()
            self._backoff_seconds = 1.0
            self._reconnect_failures = 0
            return True
        except ConnectionError:
            self._reconnect_failures += 1
            # Exponential backoff: 1, 2, 4, 8, ..., max 30
            self._backoff_seconds = min(
                self._backoff_seconds * 2,
                self._config.obd_reconnect_max_backoff,
            )

            if self._reconnect_failures >= 3:
                logger.critical(
                    "Failed to reconnect %d times, will retry in 60s",
                    self._reconnect_failures,
                )
                self._backoff_seconds = 60.0

            return False

    # --- ELM327 AT command handling ---

    async def _send_command(self, cmd: str) -> str:
        """Send a command to the ELM327 and read the response.

        Reads until the '>' prompt character. Returns the raw response
        string (everything before '>').
        """
        if self._writer is None or self._reader is None:
            raise ConnectionError("Not connected to WiCAN Pro")

        self._writer.write(cmd.encode("ascii"))
        await self._writer.drain()

        try:
            response_bytes = await asyncio.wait_for(
                self._reader.readuntil(b">"),
                timeout=self._config.obd_cmd_timeout,
            )
            # Response includes the '>' at the end, strip it
            return response_bytes.decode("ascii", errors="replace").rstrip(">").strip()
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for response to: %s", cmd.strip())
            return ""
        except asyncio.IncompleteReadError as exc:
            # Connection closed mid-read
            logger.warning("Incomplete read (connection lost): %s", exc)
            return ""

    async def _run_init_sequence(self) -> None:
        """Send the AT init commands to configure the ELM327/STN chip."""
        for cmd, expected in AT_INIT_SEQUENCE:
            response = await self._send_command(cmd)
            logger.debug("Init %s -> %r", cmd.strip(), response)

            if expected and expected.upper() not in response.upper():
                # ATZ is special -- it may return version string without "OK"
                if cmd.startswith("ATZ"):
                    if "ELM" not in response.upper() and "STN" not in response.upper():
                        logger.error(
                            "ELM327 reset failed, expected ELM/STN in response: %r",
                            response,
                        )
                        raise ConnectionError("ELM327 init failed at ATZ")
                else:
                    logger.error(
                        "Init command %s failed: expected %r in response %r",
                        cmd.strip(), expected, response,
                    )
                    raise ConnectionError(
                        f"ELM327 init failed at {cmd.strip()}"
                    )

    # --- PID polling ---

    async def _send_obd_command(self, cmd: str) -> str:
        """Send an OBD command after validating it through the safety gate.

        All commands pass through SafeOBDConnection._validate_command()
        before being sent to the adapter. This ensures only read-only
        modes (01, 02, 03, 09, 22) can reach the vehicle.
        """
        # Safety validation -- raises BlockedCommandError if not whitelisted
        self._validator._validate_command(cmd)

        return await self._send_command(cmd + "\r")

    async def _poll_one_pid(self, pid_def: PIDDef) -> bool:
        """Poll a single PID and update state. Returns True on success."""
        try:
            raw = await self._send_obd_command(pid_def.cmd)
        except (ConnectionError, BlockedCommandError) as exc:
            logger.error("Failed to send %s: %s", pid_def.cmd, exc)
            return False

        if not raw:
            return False

        # Check for error conditions that indicate connection-level issues
        upper = raw.upper()
        if "UNABLETOCONNECT" in upper or "BUSINIT" in upper:
            logger.error("Adapter reports connection issue: %r", raw)
            return False

        value = parse_elm_response(raw, pid_def)
        if value is None:
            # NO DATA or parse failure -- PID unsupported or transient error
            logger.debug("No valid data for %s: %r", pid_def.field, raw)
            return False

        state = self._pid_state[pid_def.field]
        state.value = value
        state.last_updated = time.time()
        return True

    async def _poll_mode22_cvt(self) -> None:
        """Attempt Mode 22 CVT fluid temp query. Disables on negative response."""
        if self._mode22_disabled:
            return

        try:
            raw = await self._send_obd_command("222201")
        except (ConnectionError, BlockedCommandError) as exc:
            logger.error("Mode 22 CVT query failed: %s", exc)
            return

        if not raw:
            return

        # Check for negative UDS response (7F = service not supported)
        if "7F" in raw.upper():
            logger.info(
                "Mode 22 CVT temp not supported on this ECU, disabling. Response: %r",
                raw,
            )
            self._mode22_disabled = True
            return

        temp = parse_mode22_cvt_response(raw)
        if temp is not None:
            self._cvt_temp = temp
            self._cvt_last_updated = time.time()

    async def _poll_cycle(self) -> None:
        """Run one complete cycle through all PIDs."""
        # If connection wasn't established on startup, try to connect now
        if self._writer is None:
            raise ConnectionError("Not connected to WiCAN Pro")

        for pid_def in PID_TABLE:
            if not self._running:
                return

            success = await self._poll_one_pid(pid_def)

            if success:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1

                # Circuit breaker: too many consecutive failures
                if self._consecutive_failures >= self._config.obd_circuit_breaker_threshold:
                    logger.error(
                        "Circuit breaker tripped after %d consecutive failures",
                        self._consecutive_failures,
                    )
                    self._consecutive_failures = 0
                    await asyncio.sleep(self._config.obd_circuit_breaker_cooldown)
                    reconnected = await self._reconnect()
                    if not reconnected:
                        return  # will retry in poll_loop

        # Mode 22 CVT temp at end of each cycle (optional)
        if self._config.obd_mode22_enabled and not self._mode22_disabled:
            await self._poll_mode22_cvt()

    async def _poll_loop(self) -> None:
        """Main polling loop. Runs until stop() is called."""
        while self._running:
            try:
                await self._poll_cycle()
            except ConnectionError:
                logger.error("Connection lost during poll cycle")
                if self._running:
                    reconnected = await self._reconnect()
                    if not reconnected:
                        # Keep trying in the loop
                        continue
            except Exception:
                logger.exception("Unexpected error in poll loop")
                if self._running:
                    await asyncio.sleep(1.0)
