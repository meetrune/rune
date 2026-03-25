"""Tests for the adaptive thermal management system.

Covers:
  - IIR filtering (noise rejection)
  - Band transitions with hysteresis (no oscillation)
  - Rate-of-change detection
  - Welford baseline tracking
  - Multi-level response recommendations
  - Edge cases (startup, missing data, rapid changes)
"""

from __future__ import annotations


from backend.sensors.thermal import (
    ThermalManager,
    ThermalStatus,
    WelfordTracker,
)
from backend.sensors.wittypi import (
    _decode_lm75b_temp,
    _decode_voltage,
)


# --- Witty Pi register decoding tests ---


class TestVoltageDecoding:
    def test_normal_voltage(self) -> None:
        assert _decode_voltage(13, 80) == 13.80

    def test_zero_decimal(self) -> None:
        assert _decode_voltage(12, 0) == 12.0

    def test_max_decimal(self) -> None:
        assert _decode_voltage(14, 99) == 14.99

    def test_low_voltage(self) -> None:
        assert _decode_voltage(6, 5) == 6.05

    def test_high_voltage(self) -> None:
        assert _decode_voltage(28, 50) == 28.50

    def test_zero_voltage(self) -> None:
        """0V = power disconnected."""
        assert _decode_voltage(0, 0) == 0.0


class TestLM75BDecoding:
    def test_room_temp(self) -> None:
        # 25.0C = MSB=25 (0x19), LSB=0x00
        assert _decode_lm75b_temp(25, 0x00) == 25.0

    def test_fractional_temp(self) -> None:
        # 25.125C = MSB=25, LSB=0x20 (bit 5 set = 0.125)
        assert _decode_lm75b_temp(25, 0x20) == 25.125

    def test_half_degree(self) -> None:
        # 25.5C = MSB=25, LSB=0x80 (bit 7 set = 0.5)
        assert _decode_lm75b_temp(25, 0x80) == 25.5

    def test_all_fractional_bits(self) -> None:
        # 25.875C = MSB=25, LSB=0xE0 (bits 7,6,5 = 0.5+0.25+0.125)
        assert _decode_lm75b_temp(25, 0xE0) == 25.875

    def test_negative_temp(self) -> None:
        # -10C = MSB=0xF6 (246 unsigned = -10 signed), LSB=0x00
        assert _decode_lm75b_temp(0xF6, 0x00) == -10.0

    def test_negative_fractional(self) -> None:
        # -10.5C = MSB=0xF6, LSB=0x80
        assert _decode_lm75b_temp(0xF6, 0x80) == -10.5

    def test_zero(self) -> None:
        assert _decode_lm75b_temp(0, 0) == 0.0

    def test_max_positive(self) -> None:
        # 125C = MSB=125 (0x7D), LSB=0x00
        assert _decode_lm75b_temp(125, 0x00) == 125.0

    def test_min_negative(self) -> None:
        # -55C = MSB=0xC9 (201 unsigned = -55 signed), LSB=0x00
        assert _decode_lm75b_temp(0xC9, 0x00) == -55.0

    def test_ignores_lower_bits(self) -> None:
        # Lower 5 bits of LSB should be ignored
        assert _decode_lm75b_temp(25, 0x9F) == _decode_lm75b_temp(25, 0x80)


# --- Welford tracker tests ---


class TestWelfordTracker:
    def test_mean_of_constant(self) -> None:
        w = WelfordTracker()
        for _ in range(100):
            w.update(13.5)
        assert abs(w.mean - 13.5) < 1e-10

    def test_stddev_of_constant(self) -> None:
        w = WelfordTracker()
        for _ in range(100):
            w.update(13.5)
        assert w.stddev < 1e-10

    def test_known_distribution(self) -> None:
        w = WelfordTracker()
        values = [10, 20, 30, 40, 50]
        for v in values:
            w.update(v)
        assert abs(w.mean - 30.0) < 1e-10

    def test_z_score_at_mean(self) -> None:
        w = WelfordTracker()
        for v in [10, 20, 30, 40, 50]:
            w.update(v)
        assert abs(w.z_score(30.0)) < 1e-10

    def test_z_score_returns_zero_when_insufficient_data(self) -> None:
        w = WelfordTracker()
        w.update(10)
        assert w.z_score(100) == 0.0  # need 30+ samples

    def test_z_score_detects_anomaly(self) -> None:
        w = WelfordTracker()
        # Build baseline around 13.5V +/- 0.3V
        import random
        random.seed(42)
        for _ in range(100):
            w.update(13.5 + random.gauss(0, 0.3))
        # 10V is way outside normal
        assert abs(w.z_score(10.0)) > 5.0


# --- Thermal manager tests ---


class TestThermalBandTransitions:
    """All band tests use simulated 1-second ticks via _now parameter."""

    def _make_manager(self) -> ThermalManager:
        mgr = ThermalManager()
        mgr._startup_ambient = 25.0
        mgr._startup_complete = True
        mgr._last_update = 0.0  # reset so first dt is meaningful
        return mgr

    def _tick(self, mgr: ThermalManager, cpu: float, arm: float, n: int, start_t: float = 1.0) -> object:
        state = None
        for i in range(n):
            state = mgr.update(cpu_temp_c=cpu, armrest_temp_c=arm, _now=start_t + i)
        return state

    def test_starts_green(self) -> None:
        mgr = self._make_manager()
        state = self._tick(mgr, 50.0, 25.0, 1)
        assert state.cpu_status == ThermalStatus.GREEN
        assert state.overall_status == ThermalStatus.GREEN

    def test_cpu_enters_yellow(self) -> None:
        mgr = self._make_manager()
        state = self._tick(mgr, 68.0, 25.0, 30)
        assert state.cpu_status == ThermalStatus.YELLOW

    def test_cpu_enters_orange(self) -> None:
        mgr = self._make_manager()
        state = self._tick(mgr, 75.0, 25.0, 40)
        assert state.cpu_status == ThermalStatus.ORANGE

    def test_cpu_enters_red(self) -> None:
        mgr = self._make_manager()
        state = self._tick(mgr, 80.0, 25.0, 50)
        assert state.cpu_status == ThermalStatus.RED

    def test_cpu_enters_danger(self) -> None:
        mgr = self._make_manager()
        state = self._tick(mgr, 85.0, 25.0, 60)
        assert state.should_shutdown is True
        assert state.cpu_status == ThermalStatus.DANGER

    def test_hysteresis_prevents_oscillation(self) -> None:
        """At the yellow boundary (65C), temp shouldn't flip status."""
        mgr = self._make_manager()
        # Push into yellow
        self._tick(mgr, 68.0, 25.0, 30, start_t=1.0)
        # Hover at 62C -- above exit (60C) but below entry (65C)
        state = self._tick(mgr, 62.0, 25.0, 30, start_t=31.0)
        assert state.cpu_status == ThermalStatus.YELLOW

    def test_drops_below_hysteresis(self) -> None:
        """Dropping below exit_temp should de-escalate."""
        mgr = self._make_manager()
        # Push into yellow
        self._tick(mgr, 68.0, 25.0, 30, start_t=1.0)
        # Drop well below exit (60C)
        state = self._tick(mgr, 50.0, 25.0, 60, start_t=31.0)
        assert state.cpu_status == ThermalStatus.GREEN


class TestArmrestBands:
    def _mgr(self) -> ThermalManager:
        mgr = ThermalManager()
        mgr._startup_ambient = 25.0
        mgr._startup_complete = True
        mgr._last_update = 0.0
        return mgr

    def test_armrest_yellow_at_40c(self) -> None:
        mgr = self._mgr()
        for i in range(30):
            state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=43.0, _now=1.0 + i)
        assert state.armrest_status == ThermalStatus.YELLOW

    def test_armrest_orange_at_50c(self) -> None:
        mgr = self._mgr()
        for i in range(40):
            state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=52.0, _now=1.0 + i)
        assert state.armrest_status == ThermalStatus.ORANGE

    def test_armrest_danger_at_65c(self) -> None:
        mgr = self._mgr()
        for i in range(60):
            state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=65.0, _now=1.0 + i)
        assert state.armrest_status == ThermalStatus.DANGER
        assert state.should_shutdown is True


class TestOverallStatus:
    def test_worst_of_both(self) -> None:
        mgr = ThermalManager()
        mgr._startup_ambient = 25.0
        mgr._startup_complete = True
        mgr._last_update = 0.0
        for i in range(50):
            state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=52.0, _now=1.0 + i)
        assert state.overall_status == ThermalStatus.ORANGE
        assert state.cpu_status == ThermalStatus.GREEN


class TestWSHzRecommendation:
    def _mgr(self) -> ThermalManager:
        mgr = ThermalManager()
        mgr._startup_complete = True
        mgr._last_update = 0.0
        return mgr

    def test_green_is_10hz(self) -> None:
        mgr = self._mgr()
        state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=25.0, _now=1.0)
        assert state.recommended_ws_hz == 10

    def test_orange_is_5hz(self) -> None:
        mgr = self._mgr()
        for i in range(50):
            state = mgr.update(cpu_temp_c=75.0, armrest_temp_c=25.0, _now=1.0 + i)
        assert state.recommended_ws_hz == 5

    def test_red_is_2hz(self) -> None:
        mgr = self._mgr()
        for i in range(60):
            state = mgr.update(cpu_temp_c=80.0, armrest_temp_c=25.0, _now=1.0 + i)
        assert state.recommended_ws_hz == 2


class TestRateOfChange:
    def test_stable_temp_has_zero_rate(self) -> None:
        mgr = ThermalManager()
        mgr._startup_complete = True
        mgr._last_update = 0.0
        for i in range(60):
            state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=25.0, _now=1.0 + i)
        assert abs(state.cpu_rate_per_min) < 0.5

    def test_rising_temp_detected(self) -> None:
        mgr = ThermalManager()
        mgr._startup_complete = True
        mgr._last_update = 0.0
        # Simulate 1C/sec rise over 30 seconds (= 60C/min)
        for i in range(30):
            state = mgr.update(cpu_temp_c=50.0 + i * 1.0, armrest_temp_c=25.0, _now=1.0 + i)
        # IIR dampens it, but regression on filtered values should still show a rise
        assert state.cpu_rate_per_min > 5.0


class TestIIRFilter:
    def test_filter_smooths_spike(self) -> None:
        mgr = ThermalManager()
        mgr._startup_complete = True
        mgr._last_update = 0.0
        # Steady at 50C for 20s
        for i in range(20):
            mgr.update(cpu_temp_c=50.0, armrest_temp_c=25.0, _now=1.0 + i)
        # Sudden spike to 90C
        state = mgr.update(cpu_temp_c=90.0, armrest_temp_c=25.0, _now=21.0)
        # Filtered value should NOT jump to 90 immediately
        # With tau=5, alpha = 1/(5+1) = 0.167, so filtered = 50 + 0.167*40 = 56.7
        assert state.cpu_temp_filtered < 60.0

    def test_filter_converges(self) -> None:
        mgr = ThermalManager()
        mgr._startup_complete = True
        mgr._last_update = 0.0
        for i in range(100):
            state = mgr.update(cpu_temp_c=75.0, armrest_temp_c=25.0, _now=1.0 + i)
        assert abs(state.cpu_temp_filtered - 75.0) < 1.0


class TestNoneHandling:
    def test_none_cpu_temp(self) -> None:
        mgr = ThermalManager()
        state = mgr.update(cpu_temp_c=None, armrest_temp_c=25.0, _now=1.0)
        assert state.cpu_status == ThermalStatus.GREEN

    def test_none_armrest_temp(self) -> None:
        mgr = ThermalManager()
        state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=None, _now=1.0)
        assert state.armrest_status == ThermalStatus.GREEN

    def test_all_none(self) -> None:
        mgr = ThermalManager()
        state = mgr.update(cpu_temp_c=None, armrest_temp_c=None, _now=1.0)
        assert state.overall_status == ThermalStatus.GREEN
        assert state.should_shutdown is False


class TestStartupAmbient:
    def test_records_ambient_after_10_samples(self) -> None:
        mgr = ThermalManager()
        mgr._last_update = 0.0
        for i in range(10):
            mgr.update(cpu_temp_c=50.0, armrest_temp_c=30.0, _now=1.0 + i)
        assert mgr._startup_ambient is not None
        assert abs(mgr._startup_ambient - 30.0) < 0.5


class TestThermalMessages:
    def test_green_has_no_message(self) -> None:
        mgr = ThermalManager()
        mgr._startup_complete = True
        state = mgr.update(cpu_temp_c=50.0, armrest_temp_c=25.0, _now=1.0)
        assert state.message == ""

    def test_danger_has_shutdown_message(self) -> None:
        mgr = ThermalManager()
        mgr._startup_complete = True
        mgr._last_update = 0.0
        for i in range(60):
            state = mgr.update(cpu_temp_c=85.0, armrest_temp_c=25.0, _now=1.0 + i)
        assert "shut" in state.message.lower()
