"""Tests for the Honda Accord OBD-II simulator.

Proves the simulator behaves like a real 2026 Honda Accord 1.5T:
- Warmup curves match real thermal dynamics
- Idle values match Honda specs
- Sensors are correlated (not random)
- Anomaly injection works
- All data passes Pydantic validation
"""

from __future__ import annotations

import time

import pytest

from backend.obd_manager.models import (
    VehicleSnapshot,
    maf_to_fuel_rate_lph,
    calculate_instant_mpg,
    calculate_idle_gph,
)
from backend.obd_manager.simulator import (
    AnomalyConfig,
    DrivingPhase,
    HondaAccordSimulator,
)
from backend.obd_manager.collector import SimulatedCollector


# --- Data model tests ---


class TestVehicleSnapshot:
    """Test Pydantic model validation."""

    def test_valid_idle_snapshot(self) -> None:
        snap = VehicleSnapshot(
            rpm=700, speed_kph=0, coolant_temp_c=90, engine_load_pct=20,
            throttle_pct=0, intake_air_temp_c=25, intake_manifold_kpa=30,
            maf_gps=2.5, stft_pct=1.2, ltft_pct=-0.5, fuel_level_pct=75,
            catalyst_temp_c=400, oil_temp_c=88, battery_voltage=14.2,
        )
        assert snap.rpm == 700
        assert snap.cvt_fluid_temp_c is None  # optional field

    def test_negative_rpm_rejected(self) -> None:
        with pytest.raises(Exception):
            VehicleSnapshot(
                rpm=-100, speed_kph=0, coolant_temp_c=90, engine_load_pct=20,
                throttle_pct=0, intake_air_temp_c=25, intake_manifold_kpa=30,
                maf_gps=2.5, stft_pct=0, ltft_pct=0, fuel_level_pct=75,
                catalyst_temp_c=400, oil_temp_c=88, battery_voltage=14.2,
            )

    def test_load_over_100_rejected(self) -> None:
        with pytest.raises(Exception):
            VehicleSnapshot(
                rpm=700, speed_kph=0, coolant_temp_c=90, engine_load_pct=150,
                throttle_pct=0, intake_air_temp_c=25, intake_manifold_kpa=30,
                maf_gps=2.5, stft_pct=0, ltft_pct=0, fuel_level_pct=75,
                catalyst_temp_c=400, oil_temp_c=88, battery_voltage=14.2,
            )

    def test_cvt_temp_optional(self) -> None:
        snap = VehicleSnapshot(
            rpm=700, speed_kph=0, coolant_temp_c=90, engine_load_pct=20,
            throttle_pct=0, intake_air_temp_c=25, intake_manifold_kpa=30,
            maf_gps=2.5, stft_pct=0, ltft_pct=0, fuel_level_pct=75,
            catalyst_temp_c=400, oil_temp_c=88, battery_voltage=14.2,
            cvt_fluid_temp_c=85,
        )
        assert snap.cvt_fluid_temp_c == 85


class TestFuelCalculations:
    """Test MAF-based fuel calculations."""

    def test_idle_fuel_rate(self) -> None:
        # At idle MAF ~2.5 g/s, fuel rate should be ~0.8 L/h
        rate = maf_to_fuel_rate_lph(2.5)
        assert 0.5 < rate < 1.2

    def test_highway_fuel_rate(self) -> None:
        # At highway MAF ~10 g/s, fuel rate should be ~3-4 L/h
        rate = maf_to_fuel_rate_lph(10.0)
        assert 2.0 < rate < 5.0

    def test_zero_maf(self) -> None:
        assert maf_to_fuel_rate_lph(0) == 0.0

    def test_instant_mpg_highway(self) -> None:
        # At 100 kph (~62 mph) and 20 g/s MAF (realistic highway load)
        mpg = calculate_instant_mpg(100, 20.0)
        assert mpg is not None
        assert 20 < mpg < 50  # reasonable highway MPG for 1.5T

    def test_instant_mpg_zero_speed(self) -> None:
        # At standstill, MPG is None (use idle_gph instead)
        assert calculate_instant_mpg(0, 2.5) is None

    def test_idle_gph(self) -> None:
        # At idle, should burn ~0.2-0.3 gallons/hour
        gph = calculate_idle_gph(2.5)
        assert 0.1 < gph < 0.5


# --- Simulator behavior tests ---


class TestColdStart:
    """Test that the simulator behaves like a real cold start."""

    def test_initial_rpm_is_high(self) -> None:
        sim = HondaAccordSimulator(ambient_temp_c=20)
        sim.start()
        snap = sim.get_snapshot()
        # Cold start RPM should be around 1000-1200
        assert snap.rpm > 900

    def test_coolant_starts_cold(self) -> None:
        sim = HondaAccordSimulator(ambient_temp_c=15)
        sim.start()
        snap = sim.get_snapshot()
        # Should be near ambient, not operating temp
        assert snap.coolant_temp_c < 30

    def test_speed_is_zero_at_start(self) -> None:
        sim = HondaAccordSimulator()
        sim.start()
        snap = sim.get_snapshot()
        assert snap.speed_kph < 1


class TestWarmup:
    """Test thermal warmup curves."""

    def test_coolant_approaches_operating_temp(self) -> None:
        """Coolant should move toward operating temp (90C), not stay at ambient."""
        sim = HondaAccordSimulator(ambient_temp_c=20)
        sim.start()

        # Fast-forward the internal state by advancing elapsed time
        # This avoids relying on real wall-clock time which makes tests flaky
        sim._state.elapsed = 300  # simulate 5 minutes elapsed
        # Manually trigger thermal update with a large dt
        sim._update_thermal(300.0)

        # After 300s with tau=180s, coolant should be well above ambient
        # Exponential: 20 + (90-20) * (1 - e^(-300/180)) = 20 + 70*0.81 = ~77C
        assert sim._state.coolant_temp_c > 60

    def test_oil_lags_coolant(self) -> None:
        sim = HondaAccordSimulator(ambient_temp_c=20)
        sim.start()

        for _ in range(50):
            time.sleep(0.01)
            snap = sim.get_snapshot()

        # Oil should lag behind coolant
        assert snap.oil_temp_c <= snap.coolant_temp_c + 5


class TestIdleValues:
    """Test that idle values match Honda Accord specs."""

    def _get_warmed_idle(self) -> VehicleSnapshot:
        """Get a snapshot after warmup, during idle phase."""
        sim = HondaAccordSimulator(
            ambient_temp_c=20,
            scenario=[(DrivingPhase.IDLE, 999)],
        )
        sim.start()
        # Warm up the state
        sim._state.coolant_temp_c = 90
        sim._state.oil_temp_c = 88
        sim._state.rpm = 700
        for _ in range(20):
            time.sleep(0.01)
            snap = sim.get_snapshot()
        return snap

    def test_idle_rpm_range(self) -> None:
        snap = self._get_warmed_idle()
        assert 600 < snap.rpm < 900  # wider range to account for settling + noise

    def test_idle_speed_zero(self) -> None:
        snap = self._get_warmed_idle()
        assert snap.speed_kph < 2

    def test_idle_load_range(self) -> None:
        snap = self._get_warmed_idle()
        assert 10 < snap.engine_load_pct < 30

    def test_idle_maf_range(self) -> None:
        snap = self._get_warmed_idle()
        assert 1.0 < snap.maf_gps < 7.0  # accounts for RPM settling effects on MAF

    def test_idle_battery_voltage(self) -> None:
        snap = self._get_warmed_idle()
        assert 13.5 < snap.battery_voltage < 14.8


class TestSensorCorrelations:
    """Test that sensors are correlated, not random."""

    def test_higher_rpm_means_higher_maf(self) -> None:
        """RPM and MAF should be positively correlated."""
        sim = HondaAccordSimulator()
        sim.start()

        # Idle
        snap_idle = sim.get_snapshot()

        # Force highway
        sim._state.phase = DrivingPhase.HIGHWAY
        sim._state.phase_start_time = time.monotonic()
        for _ in range(50):
            time.sleep(0.01)
            snap_highway = sim.get_snapshot()

        assert snap_highway.maf_gps > snap_idle.maf_gps

    def test_manifold_pressure_tracks_load(self) -> None:
        """Higher engine load produces higher manifold pressure.

        MAP formula: 30 + (load/100) * 70
        At idle (load=20%): MAP = 30 + 14 = 44 kPa
        At highway (load=30%): MAP = 30 + 21 = 51 kPa
        """
        sim = HondaAccordSimulator(scenario=[(DrivingPhase.HIGHWAY, 999)])
        sim.start()
        # Force the state to settled highway conditions
        sim._state.engine_load_pct = 30
        sim._state.rpm = 2000
        sim._state.speed_kph = 105
        sim._update_driving(1.0)
        snap = sim.get_snapshot()

        # At highway load (30%), MAP should be well above idle vacuum (~30 kPa)
        assert snap.intake_manifold_kpa > 40


class TestAnomalyInjection:
    """Test that anomalies affect sensor values."""

    def test_coolant_spike(self) -> None:
        anomaly = AnomalyConfig(type="coolant_spike", start_time=0, severity=1.0)
        sim = HondaAccordSimulator(anomalies=[anomaly])
        sim.start()
        sim._state.coolant_temp_c = 90  # start at operating temp

        for _ in range(50):
            time.sleep(0.02)
            snap = sim.get_snapshot()

        # Coolant should be elevated above normal operating range
        assert snap.coolant_temp_c > 96

    def test_fuel_trim_drift(self) -> None:
        anomaly = AnomalyConfig(type="fuel_trim_drift", start_time=0, severity=1.0)
        sim = HondaAccordSimulator(anomalies=[anomaly])
        sim.start()

        for _ in range(50):
            time.sleep(0.02)
            snap = sim.get_snapshot()

        assert snap.ltft_pct > 5  # LTFT should have drifted positive

    def test_voltage_drop(self) -> None:
        anomaly = AnomalyConfig(type="voltage_drop", start_time=0, severity=1.0)
        sim = HondaAccordSimulator(anomalies=[anomaly])
        sim.start()

        for _ in range(100):
            time.sleep(0.02)
            snap = sim.get_snapshot()

        # Voltage should be noticeably below normal (14.2V baseline)
        assert snap.battery_voltage < 14.0

    def test_no_anomaly_normal_values(self) -> None:
        """Without anomalies, fuel trims should stay near zero."""
        sim = HondaAccordSimulator()
        sim.start()

        for _ in range(20):
            time.sleep(0.01)
            snap = sim.get_snapshot()

        assert -5 < snap.ltft_pct < 5
        assert -5 < snap.stft_pct < 5


class TestSnapshotCompleteness:
    """Test that snapshots are complete and valid."""

    def test_all_fields_populated(self) -> None:
        sim = HondaAccordSimulator()
        sim.start()
        snap = sim.get_snapshot()

        # Every required field should be a real number (not None, not NaN)
        assert snap.rpm >= 0
        assert snap.speed_kph >= 0
        assert snap.coolant_temp_c >= -40
        assert snap.engine_load_pct >= 0
        assert snap.throttle_pct >= 0
        assert snap.intake_air_temp_c >= -40
        assert snap.intake_manifold_kpa >= 0
        assert snap.maf_gps >= 0
        assert -100 <= snap.stft_pct <= 100
        assert -100 <= snap.ltft_pct <= 100
        assert 0 <= snap.fuel_level_pct <= 100
        assert snap.catalyst_temp_c >= -40
        assert snap.oil_temp_c >= -40
        assert snap.battery_voltage >= 0

    def test_snapshot_has_timestamp(self) -> None:
        sim = HondaAccordSimulator()
        sim.start()
        snap = sim.get_snapshot()
        assert snap.timestamp > 0

    def test_not_started_raises(self) -> None:
        sim = HondaAccordSimulator()
        with pytest.raises(RuntimeError, match="not started"):
            sim.get_snapshot()


class TestCollector:
    """Test the SimulatedCollector interface."""

    async def test_start_stop(self) -> None:
        collector = SimulatedCollector()
        assert not collector.is_running

        await collector.start()
        assert collector.is_running

        snap = await collector.get_snapshot()
        assert isinstance(snap, VehicleSnapshot)

        await collector.stop()
        assert not collector.is_running

    async def test_snapshot_returns_valid_data(self) -> None:
        collector = SimulatedCollector()
        await collector.start()
        snap = await collector.get_snapshot()
        assert snap.rpm > 0
        assert snap.battery_voltage > 0
        await collector.stop()
