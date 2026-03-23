"""Tests for SafeOBDConnection -- the safety whitelist.

These tests prove that:
1. Every allowed mode passes through validation
2. Every blocked mode raises BlockedCommandError
3. Unknown modes (not in either list) are also blocked
4. Edge cases (casing, whitespace, empty strings) are handled
"""

from __future__ import annotations

import pytest

from backend.obd_manager.connection import (
    ALLOWED_MODES,
    BLOCKED_MODES,
    BlockedCommandError,
    SafeOBDConnection,
    extract_mode,
)


# --- extract_mode tests ---


class TestExtractMode:
    """Test mode extraction from various command string formats."""

    def test_simple_mode(self) -> None:
        assert extract_mode("01") == "01"

    def test_mode_with_pid(self) -> None:
        assert extract_mode("01 0C") == "01"

    def test_concatenated_format(self) -> None:
        assert extract_mode("010C") == "01"

    def test_mode_22_with_pid(self) -> None:
        assert extract_mode("22 2201") == "22"

    def test_lowercase(self) -> None:
        assert extract_mode("0a") == "0A"

    def test_mixed_case(self) -> None:
        assert extract_mode("2e 0001") == "2E"

    def test_leading_trailing_whitespace(self) -> None:
        assert extract_mode("  01  0C  ") == "01"

    def test_multiple_spaces_between(self) -> None:
        assert extract_mode("01   0C   00") == "01"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            extract_mode("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            extract_mode("   ")

    def test_invalid_hex_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            extract_mode("ZZ")


# --- Validation tests ---


class TestValidateCommand:
    """Test that SafeOBDConnection validates modes correctly."""

    def setup_method(self) -> None:
        self.conn = SafeOBDConnection()

    @pytest.mark.parametrize("mode", sorted(ALLOWED_MODES))
    def test_allowed_modes_pass(self, mode: str) -> None:
        """Every mode in ALLOWED_MODES should pass validation."""
        result = self.conn._validate_command(f"{mode} 00")
        assert result == mode

    @pytest.mark.parametrize("mode", sorted(BLOCKED_MODES))
    def test_blocked_modes_raise(self, mode: str) -> None:
        """Every mode in BLOCKED_MODES must raise BlockedCommandError."""
        with pytest.raises(BlockedCommandError, match="BLOCKED"):
            self.conn._validate_command(f"{mode} 00")

    @pytest.mark.parametrize("mode", ["05", "06", "07", "0A", "0B", "FF"])
    def test_unknown_modes_blocked(self, mode: str) -> None:
        """Modes not in either list should also be blocked (whitelist approach)."""
        with pytest.raises(BlockedCommandError, match="BLOCKED"):
            self.conn._validate_command(f"{mode} 00")


class TestAllowedModeVariations:
    """Test that allowed modes work with various formatting."""

    def setup_method(self) -> None:
        self.conn = SafeOBDConnection()

    def test_mode_01_with_pid(self) -> None:
        assert self.conn._validate_command("01 0C") == "01"

    def test_mode_01_lowercase(self) -> None:
        assert self.conn._validate_command("01 0c") == "01"

    def test_mode_02_freeze_frame(self) -> None:
        assert self.conn._validate_command("02 0C 01") == "02"

    def test_mode_03_dtc_read(self) -> None:
        assert self.conn._validate_command("03") == "03"

    def test_mode_09_vin(self) -> None:
        assert self.conn._validate_command("09 02") == "09"

    def test_mode_22_honda_cvt_temp(self) -> None:
        """Honda proprietary: CVT fluid temp via Mode 22."""
        assert self.conn._validate_command("22 2201") == "22"

    def test_mode_22_lowercase(self) -> None:
        assert self.conn._validate_command("22 2201") == "22"

    def test_extra_whitespace(self) -> None:
        assert self.conn._validate_command("  01  0C  ") == "01"

    def test_concatenated_allowed(self) -> None:
        assert self.conn._validate_command("010C") == "01"


class TestBlockedModeMessages:
    """Test that blocked modes produce clear error messages."""

    def setup_method(self) -> None:
        self.conn = SafeOBDConnection()

    def test_mode_04_clear_dtcs(self) -> None:
        """Mode 04 clears DTCs -- must never be allowed."""
        with pytest.raises(BlockedCommandError, match="Mode 04"):
            self.conn._validate_command("04")

    def test_mode_2e_write_data(self) -> None:
        """Mode 2E writes data to ECU -- must never be allowed."""
        with pytest.raises(BlockedCommandError, match="Mode 2E"):
            self.conn._validate_command("2E 0001 FF")

    def test_mode_31_routine_control(self) -> None:
        """Mode 31 controls ECU routines -- must never be allowed."""
        with pytest.raises(BlockedCommandError, match="Mode 31"):
            self.conn._validate_command("31 01 FF00")

    def test_mode_27_security_access(self) -> None:
        """Mode 27 is seed/key auth -- must never be allowed."""
        with pytest.raises(BlockedCommandError, match="Mode 27"):
            self.conn._validate_command("27 01")

    def test_error_message_includes_whitelist(self) -> None:
        """Error message should tell the user what IS allowed."""
        with pytest.raises(BlockedCommandError, match="read-only") as exc_info:
            self.conn._validate_command("04")
        assert "01" in str(exc_info.value)
        assert "22" in str(exc_info.value)


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def setup_method(self) -> None:
        self.conn = SafeOBDConnection()

    def test_empty_command(self) -> None:
        with pytest.raises(ValueError):
            self.conn._validate_command("")

    def test_whitespace_command(self) -> None:
        with pytest.raises(ValueError):
            self.conn._validate_command("   ")

    def test_not_connected_is_false(self) -> None:
        """New connection should report not connected."""
        assert not self.conn.is_connected

    def test_initial_status(self) -> None:
        assert self.conn.status == "Not initialized"

    def test_blocked_modes_documented(self) -> None:
        """Ensure BLOCKED_MODES matches the PRD exactly."""
        expected = {"04", "08", "10", "27", "2E", "31", "3E"}
        assert BLOCKED_MODES == expected

    def test_allowed_modes_documented(self) -> None:
        """Ensure ALLOWED_MODES matches the PRD exactly."""
        expected = {"01", "02", "03", "09", "22"}
        assert ALLOWED_MODES == expected

    def test_no_overlap(self) -> None:
        """Allowed and blocked sets must never overlap."""
        assert ALLOWED_MODES.isdisjoint(BLOCKED_MODES)


class TestPublicAPI:
    """Test the public query() and send_raw() methods.

    These test the actual code paths that will be called in production,
    not just the internal _validate_command(). Critical because if someone
    refactors query() and breaks the validation line, the _validate_command
    tests would still pass while the safety gate is open.
    """

    def setup_method(self) -> None:
        self.conn = SafeOBDConnection()

    async def test_query_not_connected_raises(self) -> None:
        """query() on unconnected adapter raises ConnectionError."""
        import obd
        cmd = obd.OBDCommand("RPM", "RPM", b"\x01\x0c", 6,
                             lambda m: m, obd.ECU.ENGINE, True)
        with pytest.raises(ConnectionError, match="Not connected"):
            await self.conn.query(cmd)

    async def test_query_blocks_write_mode(self) -> None:
        """query() with a Mode 04 command must raise BlockedCommandError."""
        import obd
        bad_cmd = obd.OBDCommand("CLEAR", "Clear DTCs", b"\x04", 0,
                                 lambda m: m, obd.ECU.ALL, False)
        with pytest.raises(BlockedCommandError, match="BLOCKED"):
            await self.conn.query(bad_cmd)

    async def test_send_raw_not_connected_raises(self) -> None:
        """send_raw() on unconnected adapter raises ConnectionError."""
        with pytest.raises(ConnectionError, match="Not connected"):
            await self.conn.send_raw("01 0C")

    async def test_send_raw_blocks_write_mode(self) -> None:
        """send_raw() with Mode 04 must raise BlockedCommandError."""
        with pytest.raises(BlockedCommandError, match="BLOCKED"):
            await self.conn.send_raw("04")

    async def test_send_raw_blocks_mode_2e(self) -> None:
        """send_raw() with Mode 2E (write data) must raise BlockedCommandError."""
        with pytest.raises(BlockedCommandError, match="BLOCKED"):
            await self.conn.send_raw("2E 0001 FF")

    async def test_send_raw_allows_mode_22(self) -> None:
        """send_raw() with Mode 22 (Honda proprietary read) passes validation
        but raises ConnectionError because we're not connected."""
        with pytest.raises(ConnectionError):
            await self.conn.send_raw("22 2201")

    async def test_send_raw_invalid_hex_raises(self) -> None:
        """send_raw() with invalid hex bytes raises ValueError."""
        with pytest.raises(ValueError, match="Invalid hex"):
            await self.conn.send_raw("22 GGGG")
