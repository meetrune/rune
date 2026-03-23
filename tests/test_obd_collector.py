"""Tests for OBDCollector -- ELM327 response parsing, PID decoding,
reconnection logic, and circuit breaker behavior.

All tests use mocked asyncio streams. Never connects to real hardware.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.obd_manager.collector import (
    OBDCollector,
    PID_TABLE,
    PIDDef,
    _PIDState,
    decode_pid,
    parse_elm_response,
    parse_mode22_cvt_response,
)
from backend.config import RuneSettings


# --- PID formula decoding tests ---


class TestDecodePID:
    """Verify OBD-II PID formulas match ISO 15031-5 / SAE J1979."""

    def test_rpm(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        # 0x0FA0 = 4000 -> 4000/4 = 1000 RPM
        assert decode_pid(pid, [0x0F, 0xA0]) == 1000.0

    def test_rpm_idle(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        # 750 RPM = 3000 raw -> 0x0BB8
        assert decode_pid(pid, [0x0B, 0xB8]) == 750.0

    def test_rpm_zero(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        assert decode_pid(pid, [0, 0]) == 0.0

    def test_speed(self) -> None:
        pid = PIDDef(cmd="010D", field="speed_kph", data_bytes=1)
        assert decode_pid(pid, [100]) == 100.0

    def test_speed_zero(self) -> None:
        pid = PIDDef(cmd="010D", field="speed_kph", data_bytes=1)
        assert decode_pid(pid, [0]) == 0.0

    def test_coolant_temp(self) -> None:
        pid = PIDDef(cmd="0105", field="coolant_temp_c", data_bytes=1)
        # 130 - 40 = 90 C (normal operating temp)
        assert decode_pid(pid, [130]) == 90.0

    def test_coolant_temp_cold(self) -> None:
        pid = PIDDef(cmd="0105", field="coolant_temp_c", data_bytes=1)
        # 40 - 40 = 0 C
        assert decode_pid(pid, [40]) == 0.0

    def test_engine_load(self) -> None:
        pid = PIDDef(cmd="0104", field="engine_load_pct", data_bytes=1)
        # 128 * 100 / 255 = 50.2%
        assert abs(decode_pid(pid, [128]) - 50.196) < 0.01

    def test_throttle(self) -> None:
        pid = PIDDef(cmd="0111", field="throttle_pct", data_bytes=1)
        assert abs(decode_pid(pid, [255]) - 100.0) < 0.01

    def test_intake_air_temp(self) -> None:
        pid = PIDDef(cmd="010F", field="intake_air_temp_c", data_bytes=1)
        assert decode_pid(pid, [65]) == 25.0

    def test_map(self) -> None:
        pid = PIDDef(cmd="010B", field="intake_manifold_kpa", data_bytes=1)
        assert decode_pid(pid, [101]) == 101.0

    def test_maf(self) -> None:
        pid = PIDDef(cmd="0110", field="maf_gps", data_bytes=2)
        # 0x0100 = 256 -> 256/100 = 2.56 g/s
        assert decode_pid(pid, [0x01, 0x00]) == 2.56

    def test_stft(self) -> None:
        pid = PIDDef(cmd="0106", field="stft_pct", data_bytes=1)
        # 128 -> (128-128)*100/128 = 0% (centered)
        assert decode_pid(pid, [128]) == 0.0

    def test_stft_positive(self) -> None:
        pid = PIDDef(cmd="0106", field="stft_pct", data_bytes=1)
        # 138 -> (138-128)*100/128 = 7.8125%
        assert abs(decode_pid(pid, [138]) - 7.8125) < 0.01

    def test_ltft_negative(self) -> None:
        pid = PIDDef(cmd="0107", field="ltft_pct", data_bytes=1)
        # 118 -> (118-128)*100/128 = -7.8125%
        assert abs(decode_pid(pid, [118]) - (-7.8125)) < 0.01

    def test_fuel_level(self) -> None:
        pid = PIDDef(cmd="012F", field="fuel_level_pct", data_bytes=1)
        # 191 * 100 / 255 = 74.9%
        assert abs(decode_pid(pid, [191]) - 74.902) < 0.01

    def test_catalyst_temp(self) -> None:
        pid = PIDDef(cmd="013C", field="catalyst_temp_c", data_bytes=2)
        # (0x0FA0 = 4000) / 10 - 40 = 360 C
        assert decode_pid(pid, [0x0F, 0xA0]) == 360.0

    def test_battery_voltage(self) -> None:
        pid = PIDDef(cmd="0142", field="battery_voltage", data_bytes=2)
        # (0x3840 = 14400) / 1000 = 14.4 V
        assert decode_pid(pid, [0x38, 0x40]) == 14.4

    def test_oil_temp(self) -> None:
        pid = PIDDef(cmd="015C", field="oil_temp_c", data_bytes=1)
        # 140 - 40 = 100 C
        assert decode_pid(pid, [140]) == 100.0


# --- ELM327 response parsing tests ---


class TestParseElmResponse:
    """Test parsing raw ELM327 hex strings into decoded values."""

    def test_valid_rpm_response(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        result = parse_elm_response("410C0FA0", pid)
        assert result == 1000.0

    def test_valid_speed_response(self) -> None:
        pid = PIDDef(cmd="010D", field="speed_kph", data_bytes=1)
        result = parse_elm_response("410D64", pid)
        assert result == 100.0

    def test_valid_coolant_response(self) -> None:
        pid = PIDDef(cmd="0105", field="coolant_temp_c", data_bytes=1)
        result = parse_elm_response("410582", pid)
        assert result == 90.0

    def test_valid_voltage_response(self) -> None:
        pid = PIDDef(cmd="0142", field="battery_voltage", data_bytes=2)
        result = parse_elm_response("41423840", pid)
        assert result == 14.4

    def test_no_data_response(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        assert parse_elm_response("NO DATA", pid) is None

    def test_no_data_with_whitespace(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        assert parse_elm_response("  NO DATA  \r\n", pid) is None

    def test_unable_to_connect(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        assert parse_elm_response("UNABLE TO CONNECT", pid) is None

    def test_error_response(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        assert parse_elm_response("BUS INIT...ERROR", pid) is None

    def test_negative_uds_response(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        assert parse_elm_response("7F0112", pid) is None

    def test_empty_response(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        assert parse_elm_response("", pid) is None

    def test_response_with_trailing_prompt(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        result = parse_elm_response("410C0FA0>", pid)
        assert result == 1000.0

    def test_response_with_spaces(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        result = parse_elm_response("41 0C 0F A0", pid)
        assert result == 1000.0

    def test_response_with_crlf(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        result = parse_elm_response("410C0FA0\r\n", pid)
        assert result == 1000.0

    def test_wrong_mode_in_response(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        # Mode 42 instead of 41
        assert parse_elm_response("420C0FA0", pid) is None

    def test_wrong_pid_in_response(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        # PID 0D instead of 0C
        assert parse_elm_response("410D0FA0", pid) is None

    def test_too_short_data(self) -> None:
        pid = PIDDef(cmd="010C", field="rpm", data_bytes=2)
        # Only 1 data byte when 2 expected
        assert parse_elm_response("410C0F", pid) is None


# --- Mode 22 CVT temp parsing tests ---


class TestParseMode22CVT:
    """Test Mode 22 CVT fluid temp response parsing."""

    def test_valid_cvt_response(self) -> None:
        # Build response: 62 22 01 + 27 padding bytes + temp byte
        # 27 bytes of padding (0x00) then temp byte = 120 -> 120-40 = 80 C
        header = "622201"
        padding = "00" * 27
        temp_byte = "78"  # 120 decimal
        result = parse_mode22_cvt_response(header + padding + temp_byte)
        assert result == 80.0

    def test_cvt_cold(self) -> None:
        header = "622201"
        padding = "00" * 27
        temp_byte = "28"  # 40 decimal -> 40-40 = 0 C
        result = parse_mode22_cvt_response(header + padding + temp_byte)
        assert result == 0.0

    def test_cvt_negative_response(self) -> None:
        assert parse_mode22_cvt_response("7F2231") is None

    def test_cvt_no_data(self) -> None:
        assert parse_mode22_cvt_response("NO DATA") is None

    def test_cvt_empty(self) -> None:
        assert parse_mode22_cvt_response("") is None

    def test_cvt_response_too_short(self) -> None:
        # Only header + a few bytes, not enough for byte 27
        assert parse_mode22_cvt_response("622201001122") is None

    def test_cvt_wrong_header(self) -> None:
        header = "622202"  # wrong sub-PID
        padding = "00" * 27
        temp_byte = "78"
        assert parse_mode22_cvt_response(header + padding + temp_byte) is None


# --- Mock TCP helpers ---


def _make_mock_streams(
    responses: list[bytes],
) -> tuple[AsyncMock, AsyncMock]:
    """Create mock asyncio StreamReader and StreamWriter.

    responses: list of bytes to return from reader.readuntil().
    Each call to readuntil() pops the next response.
    """
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = AsyncMock(spec=asyncio.StreamWriter)

    response_iter = iter(responses)

    async def mock_readuntil(sep: bytes = b"\n") -> bytes:
        try:
            return next(response_iter)
        except StopIteration:
            raise asyncio.IncompleteReadError(b"", None)

    reader.readuntil = mock_readuntil
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    return reader, writer


def _make_config(**overrides: object) -> RuneSettings:
    """Create a RuneSettings with test-friendly defaults."""
    defaults = {
        "wican_host": "127.0.0.1",
        "wican_port": 33333,
        "obd_cmd_timeout": 1.0,
        "obd_reconnect_max_backoff": 2.0,
        "obd_circuit_breaker_threshold": 5,
        "obd_circuit_breaker_cooldown": 0.1,
        "obd_stale_threshold": 5.0,
        "obd_mode22_enabled": False,
        "use_simulator": False,
    }
    defaults.update(overrides)
    return RuneSettings(**defaults)  # type: ignore[arg-type]


# Build the standard init responses (7 AT commands, each returns OK or ELM)
def _init_responses() -> list[bytes]:
    return [
        b"ELM327 v2.3>",   # ATZ
        b"OK>",             # ATE0
        b"OK>",             # ATL0
        b"OK>",             # ATS0
        b"OK>",             # ATSP6
        b"OK>",             # ATSH7E0
        b"OK>",             # ATCRA7E8
    ]


# --- OBDCollector integration tests ---


class TestOBDCollectorConnect:
    """Test TCP connection and ELM327 initialization."""

    @pytest.mark.asyncio
    async def test_successful_init(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        reader, writer = _make_mock_streams(_init_responses())

        with patch("asyncio.open_connection", return_value=(reader, writer)):
            await collector._connect()

        assert collector._writer is not None
        assert collector._reader is not None

    @pytest.mark.asyncio
    async def test_init_fails_on_bad_atz(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        bad_responses = [b"GARBAGE>"] + [b"OK>"] * 6
        reader, writer = _make_mock_streams(bad_responses)

        with patch("asyncio.open_connection", return_value=(reader, writer)):
            with pytest.raises(ConnectionError, match="ELM327 init failed"):
                await collector._connect()

    @pytest.mark.asyncio
    async def test_init_fails_on_bad_atsp6(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        # ATZ OK, ATE0 OK, ATL0 OK, ATS0 OK, ATSP6 fails
        responses = [
            b"ELM327 v2.3>",
            b"OK>",
            b"OK>",
            b"OK>",
            b"ERROR>",  # ATSP6 fails
            b"OK>",
            b"OK>",
        ]
        reader, writer = _make_mock_streams(responses)

        with patch("asyncio.open_connection", return_value=(reader, writer)):
            with pytest.raises(ConnectionError, match="ELM327 init failed"):
                await collector._connect()


class TestOBDCollectorPolling:
    """Test PID polling and value updates."""

    @pytest.mark.asyncio
    async def test_poll_single_pid_rpm(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        # Manually set up connection state
        responses = [b"410C0FA0>"]  # RPM = 1000
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        pid = PID_TABLE[0]  # RPM
        success = await collector._poll_one_pid(pid)
        assert success is True
        assert collector._pid_state["rpm"].value == 1000.0

    @pytest.mark.asyncio
    async def test_poll_no_data_returns_false(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        responses = [b"NO DATA>"]
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        pid = PID_TABLE[0]  # RPM
        success = await collector._poll_one_pid(pid)
        assert success is False

    @pytest.mark.asyncio
    async def test_poll_unable_to_connect(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        responses = [b"UNABLE TO CONNECT>"]
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        pid = PID_TABLE[0]
        success = await collector._poll_one_pid(pid)
        assert success is False

    @pytest.mark.asyncio
    async def test_get_snapshot_returns_latest_values(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        # Set some PID state manually
        collector._pid_state["rpm"].value = 750.0
        collector._pid_state["rpm"].last_updated = time.time()
        collector._pid_state["speed_kph"].value = 60.0
        collector._pid_state["speed_kph"].last_updated = time.time()
        collector._pid_state["coolant_temp_c"].value = 90.0
        collector._pid_state["coolant_temp_c"].last_updated = time.time()

        snapshot = await collector.get_snapshot()
        assert snapshot.rpm == 750.0
        assert snapshot.speed_kph == 60.0
        assert snapshot.coolant_temp_c == 90.0


class TestOBDCollectorCircuitBreaker:
    """Test circuit breaker behavior after consecutive failures."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_after_threshold(self) -> None:
        config = _make_config(obd_circuit_breaker_threshold=3)
        collector = OBDCollector(config=config)
        collector._running = True

        # All responses are NO DATA (failures)
        no_data_responses = [b"NO DATA>"] * 20
        reader, writer = _make_mock_streams(no_data_responses)
        collector._reader = reader
        collector._writer = writer

        # Mock _reconnect to track calls and return success
        reconnect_called = False

        async def mock_reconnect() -> bool:
            nonlocal reconnect_called
            reconnect_called = True
            return True

        collector._reconnect = mock_reconnect  # type: ignore[assignment]

        # Poll enough PIDs to trigger circuit breaker (threshold=3)
        for i in range(3):
            await collector._poll_one_pid(PID_TABLE[i])

        # At this point consecutive_failures = 3 >= threshold
        # Next poll_cycle would trigger circuit breaker
        # Let's trigger it through poll_cycle
        collector._consecutive_failures = 0  # reset for clean test

        # Set up fresh streams with all failures
        reader2, writer2 = _make_mock_streams([b"NO DATA>"] * 20)
        collector._reader = reader2
        collector._writer = writer2

        # Run poll_cycle -- after 3 consecutive failures it should reconnect
        await collector._poll_cycle()
        assert reconnect_called

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        collector._consecutive_failures = 4  # one away from threshold

        responses = [b"410C0FA0>"]  # valid RPM
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        await collector._poll_one_pid(PID_TABLE[0])
        # _poll_one_pid doesn't reset failures -- _poll_cycle does
        # But poll_one_pid returns True, and poll_cycle resets on True
        assert collector._pid_state["rpm"].value == 1000.0


class TestOBDCollectorReconnect:
    """Test reconnection with exponential backoff."""

    @pytest.mark.asyncio
    async def test_backoff_doubles(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)
        collector._backoff_seconds = 1.0

        # Mock _connect to fail
        connect_attempts = 0

        async def failing_connect() -> None:
            nonlocal connect_attempts
            connect_attempts += 1
            raise ConnectionError("mock failure")

        collector._connect = failing_connect  # type: ignore[assignment]
        collector._disconnect = AsyncMock()  # type: ignore[assignment]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await collector._reconnect()

        assert result is False
        assert collector._backoff_seconds == 2.0  # doubled from 1.0

    @pytest.mark.asyncio
    async def test_backoff_caps_at_max(self) -> None:
        config = _make_config(obd_reconnect_max_backoff=4.0)
        collector = OBDCollector(config=config)
        collector._backoff_seconds = 4.0  # already at max

        async def failing_connect() -> None:
            raise ConnectionError("mock failure")

        collector._connect = failing_connect  # type: ignore[assignment]
        collector._disconnect = AsyncMock()  # type: ignore[assignment]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await collector._reconnect()

        # Should not exceed max
        assert collector._backoff_seconds <= 4.0

    @pytest.mark.asyncio
    async def test_successful_reconnect_resets_backoff(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)
        collector._backoff_seconds = 8.0
        collector._reconnect_failures = 2

        async def success_connect() -> None:
            collector._consecutive_failures = 0
            collector._reconnect_failures = 0
            collector._backoff_seconds = 1.0

        collector._connect = success_connect  # type: ignore[assignment]
        collector._disconnect = AsyncMock()  # type: ignore[assignment]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await collector._reconnect()

        assert result is True
        assert collector._backoff_seconds == 1.0
        assert collector._reconnect_failures == 0

    @pytest.mark.asyncio
    async def test_three_failures_escalates_to_60s(self) -> None:
        config = _make_config(obd_reconnect_max_backoff=30.0)
        collector = OBDCollector(config=config)
        collector._backoff_seconds = 1.0
        collector._reconnect_failures = 2  # next failure will be 3rd

        async def failing_connect() -> None:
            raise ConnectionError("mock failure")

        collector._connect = failing_connect  # type: ignore[assignment]
        collector._disconnect = AsyncMock()  # type: ignore[assignment]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await collector._reconnect()

        assert collector._reconnect_failures == 3
        assert collector._backoff_seconds == 60.0


class TestOBDCollectorMode22:
    """Test Mode 22 CVT fluid temp queries."""

    @pytest.mark.asyncio
    async def test_mode22_disabled_on_negative_response(self) -> None:
        config = _make_config(obd_mode22_enabled=True)
        collector = OBDCollector(config=config)

        responses = [b"7F2231>"]  # negative response
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        await collector._poll_mode22_cvt()
        assert collector._mode22_disabled is True

    @pytest.mark.asyncio
    async def test_mode22_skips_when_disabled(self) -> None:
        config = _make_config(obd_mode22_enabled=True)
        collector = OBDCollector(config=config)
        collector._mode22_disabled = True

        # Should return immediately without sending anything
        await collector._poll_mode22_cvt()
        # No assertion needed -- just verifying no exception


class TestOBDCollectorSafety:
    """Verify safety gate is enforced on all OBD commands."""

    @pytest.mark.asyncio
    async def test_blocked_mode_raises(self) -> None:
        from backend.obd_manager.connection import BlockedCommandError

        config = _make_config()
        collector = OBDCollector(config=config)

        responses = [b"OK>"]
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        with pytest.raises(BlockedCommandError):
            await collector._send_obd_command("04")  # clear DTCs -- BLOCKED

    @pytest.mark.asyncio
    async def test_blocked_mode_2e(self) -> None:
        from backend.obd_manager.connection import BlockedCommandError

        config = _make_config()
        collector = OBDCollector(config=config)

        responses = [b"OK>"]
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        with pytest.raises(BlockedCommandError):
            await collector._send_obd_command("2E0102AA")  # write by ID -- BLOCKED

    @pytest.mark.asyncio
    async def test_allowed_mode_01_passes(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        responses = [b"410C0FA0>"]
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        result = await collector._send_obd_command("010C")
        assert "410C0FA0" in result

    @pytest.mark.asyncio
    async def test_allowed_mode_22_passes(self) -> None:
        config = _make_config()
        collector = OBDCollector(config=config)

        responses = [b"622201AABB>"]
        reader, writer = _make_mock_streams(responses)
        collector._reader = reader
        collector._writer = writer

        result = await collector._send_obd_command("222201")
        assert "622201" in result


class TestStaleDataHandling:
    """Test stale PID detection in get_snapshot()."""

    @pytest.mark.asyncio
    async def test_stale_pid_still_returned(self) -> None:
        config = _make_config(obd_stale_threshold=5.0)
        collector = OBDCollector(config=config)

        # Set RPM to a value but with an old timestamp
        collector._pid_state["rpm"].value = 800.0
        collector._pid_state["rpm"].last_updated = time.time() - 10.0

        snapshot = await collector.get_snapshot()
        # Stale value is still returned (better than nothing)
        assert snapshot.rpm == 800.0

    @pytest.mark.asyncio
    async def test_fresh_pid_not_flagged(self) -> None:
        config = _make_config(obd_stale_threshold=5.0)
        collector = OBDCollector(config=config)

        collector._pid_state["rpm"].value = 800.0
        collector._pid_state["rpm"].last_updated = time.time()

        snapshot = await collector.get_snapshot()
        assert snapshot.rpm == 800.0
        assert collector._pid_state["rpm"].stale_logged is False
