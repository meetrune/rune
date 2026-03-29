"""Tests for the fuel calculator and fill-up detector."""

from __future__ import annotations

import time


from backend.fuel.calculator import FuelCalculator
from backend.fuel.fillup import FillupDetector, FillupEvent
from backend.obd_manager.models import VehicleSnapshot


def _snap(
    speed_kph: float = 0,
    maf_gps: float = 2.5,
    fuel_level_pct: float = 75.0,
    timestamp: float | None = None,
    rpm: float | None = None,
) -> VehicleSnapshot:
    """Build a minimal valid VehicleSnapshot."""
    return VehicleSnapshot(
        timestamp=timestamp or time.time(),
        rpm=rpm if rpm is not None else (700 if speed_kph == 0 else 2000),
        speed_kph=speed_kph,
        coolant_temp_c=90,
        engine_load_pct=20 if speed_kph == 0 else 30,
        throttle_pct=0 if speed_kph == 0 else 18,
        intake_air_temp_c=25,
        intake_manifold_kpa=30,
        maf_gps=maf_gps,
        stft_pct=0,
        ltft_pct=0,
        fuel_level_pct=fuel_level_pct,
        catalyst_temp_c=400,
        oil_temp_c=88,
        battery_voltage=14.2,
    )


# --- FuelCalculator tests ---


class TestTripDetection:

    def test_idle_no_trip(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        snap = _snap(speed_kph=0)
        fuel, started, ended = calc.update(snap)
        assert not started
        assert not ended
        assert not calc.is_trip_active

    def test_trip_starts_on_movement(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        snap = _snap(speed_kph=50)  # well above 5 kph threshold
        fuel, started, ended = calc.update(snap)
        assert started
        assert not ended
        assert calc.is_trip_active

    def test_low_speed_noise_no_trip(self) -> None:
        """Speed below 5 kph (GPS jitter) should NOT start a trip."""
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        snap = _snap(speed_kph=3)  # below threshold
        fuel, started, ended = calc.update(snap)
        assert not started
        assert not calc.is_trip_active

    def test_trip_accumulates_distance(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        # Start trip
        calc.update(_snap(speed_kph=100, timestamp=t))

        # Drive for 10 ticks at 100 kph, 1 second apart
        for i in range(1, 11):
            calc.update(_snap(speed_kph=100, maf_gps=15.0, timestamp=t + i))

        assert calc.current_trip is not None
        assert calc.current_trip.distance_miles > 0

    def test_trip_accumulates_fuel(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        calc.update(_snap(speed_kph=100, maf_gps=15.0, timestamp=t))
        for i in range(1, 11):
            calc.update(_snap(speed_kph=100, maf_gps=15.0, timestamp=t + i))

        assert calc.current_trip is not None
        assert calc.current_trip.fuel_gallons > 0

    def test_idle_30s_does_not_end_trip(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        # Start driving
        calc.update(_snap(speed_kph=50, timestamp=t))

        # Stop for 30 seconds
        for i in range(1, 31):
            _, _, ended = calc.update(_snap(speed_kph=0, timestamp=t + i))

        assert not ended
        assert calc.is_trip_active

    def test_engine_off_ends_trip(self) -> None:
        """RPM dropping to 0 for 10+ seconds = engine off = trip ends."""
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        # Drive for 30 seconds at 100 kph to build real distance
        for i in range(30):
            calc.update(_snap(speed_kph=100, maf_gps=15.0, timestamp=t + i))

        # Engine off (RPM=0) for 11 seconds
        ended_at = None
        for i in range(30, 42):
            _, _, ended = calc.update(_snap(speed_kph=0, rpm=0, timestamp=t + i))
            if ended:
                ended_at = i

        assert ended_at is not None
        assert not calc.is_trip_active

    def test_idle_in_traffic_no_false_end(self) -> None:
        """Engine running at idle (RPM=700, speed=0) should NOT end trip,
        even after 60+ seconds. This is the traffic/red light fix."""
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        # Drive
        for i in range(10):
            calc.update(_snap(speed_kph=80, maf_gps=12.0, timestamp=t + i))

        # Sit in traffic for 120 seconds, engine running (RPM=700)
        for i in range(10, 130):
            _, _, ended = calc.update(_snap(speed_kph=0, rpm=700, timestamp=t + i))
            assert not ended

        assert calc.is_trip_active

    def test_junk_trip_discarded(self) -> None:
        """Trip with < 0.05 miles should be silently discarded, not ended."""
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        # Barely move (6 kph for 1 second = ~0.001 miles)
        calc.update(_snap(speed_kph=6, timestamp=t))
        calc.update(_snap(speed_kph=6, timestamp=t + 1))

        # Engine off (RPM=0) for 12 seconds
        any_ended = False
        for i in range(2, 14):
            _, _, ended = calc.update(_snap(speed_kph=0, rpm=0, timestamp=t + i))
            if ended:
                any_ended = True

        # Trip should be discarded, not ended (too short distance)
        assert not any_ended
        assert not calc.is_trip_active
        assert calc.get_completed_trip_summary() is None

    def test_red_light_no_false_end(self) -> None:
        """Stop for 30s at a red light, then continue -- trip should NOT end."""
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        # Drive
        calc.update(_snap(speed_kph=50, timestamp=t))

        # Red light: stop for 30s
        for i in range(1, 31):
            calc.update(_snap(speed_kph=0, timestamp=t + i))

        # Green light: start moving again
        _, _, ended = calc.update(_snap(speed_kph=50, timestamp=t + 31))
        assert not ended
        assert calc.is_trip_active


class TestFuelSnapshot:

    def test_instant_mpg_at_highway(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()
        calc.update(_snap(speed_kph=100, maf_gps=20.0, timestamp=t))
        fuel, _, _ = calc.update(_snap(speed_kph=100, maf_gps=20.0, timestamp=t + 1))
        assert fuel.instant_mpg is not None
        assert 20 < fuel.instant_mpg < 50

    def test_instant_mpg_none_at_idle(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        fuel, _, _ = calc.update(_snap(speed_kph=0))
        assert fuel.instant_mpg is None

    def test_idle_gph_at_idle(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        fuel, _, _ = calc.update(_snap(speed_kph=0, maf_gps=2.5))
        assert fuel.idle_gph is not None
        assert 0.1 < fuel.idle_gph < 0.5

    def test_idle_gph_none_while_moving(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        fuel, _, _ = calc.update(_snap(speed_kph=50))
        assert fuel.idle_gph is None

    def test_trip_cost_calculated(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()
        calc.update(_snap(speed_kph=100, maf_gps=15.0, timestamp=t))
        for i in range(1, 11):
            fuel, _, _ = calc.update(_snap(speed_kph=100, maf_gps=15.0, timestamp=t + i))

        assert fuel.trip_cost_usd > 0
        assert fuel.trip_fuel_gal > 0
        # Cost should equal fuel * price
        assert abs(fuel.trip_cost_usd - fuel.trip_fuel_gal * 3.50) < 0.01

    def test_tank_pct_from_snapshot(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        fuel, _, _ = calc.update(_snap(fuel_level_pct=62.5))
        assert fuel.tank_pct == 62.5


class TestTripSummary:

    def test_completed_trip_summary(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()

        # Drive for 30 seconds to build real distance
        for i in range(30):
            calc.update(_snap(speed_kph=100, maf_gps=15.0, timestamp=t + i))

        # Engine off (RPM=0) for 12s to end trip
        for i in range(30, 42):
            calc.update(_snap(speed_kph=0, rpm=0, timestamp=t + i))

        summary = calc.get_completed_trip_summary()
        assert summary is not None
        assert summary["distance_miles"] > 0
        assert summary["fuel_gallons"] > 0
        assert summary["avg_mpg"] is not None

    def test_no_summary_without_completed_trip(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        assert calc.get_completed_trip_summary() is None


class TestEdgeCases:

    def test_zero_dt_safe(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()
        # Two updates at same timestamp
        calc.update(_snap(speed_kph=50, timestamp=t))
        fuel, _, _ = calc.update(_snap(speed_kph=50, timestamp=t))
        assert fuel.trip_distance_mi == 0  # no distance at dt=0

    def test_negative_dt_clamped(self) -> None:
        calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        t = time.time()
        calc.update(_snap(speed_kph=50, timestamp=t))
        # Timestamp goes backward (NTP sync)
        fuel, _, _ = calc.update(_snap(speed_kph=50, timestamp=t - 5))
        assert fuel.trip_distance_mi >= 0  # no negative distance


# --- FillupDetector tests ---


def _warmed_detector(
    tank: float = 14.8,
    price: float = 3.50,
    epa: float = 31.0,
    warmup_pct: float = 50.0,
) -> FillupDetector:
    """Create a FillupDetector past the 5-reading startup protection."""
    det = FillupDetector(tank, price, epa)
    for _ in range(5):
        det.check(_snap(fuel_level_pct=warmup_pct))
    return det


def _trigger_fillup(
    det: FillupDetector,
    new_pct: float,
    miles_since_last_fill: float | None = None,
) -> FillupEvent | None:
    """Send enough readings at new_pct to trigger multi-sample confirmation."""
    event = None
    for _ in range(4):  # 3 confirmations + 1 for margin
        event = det.check(_snap(fuel_level_pct=new_pct), miles_since_last_fill=miles_since_last_fill)
        if event is not None:
            return event
    return event


class TestFillupStartupProtection:

    def test_ignores_first_4_readings(self) -> None:
        """Fill-up detection should be suppressed during startup."""
        det = FillupDetector(14.8, 3.50, 31.0)
        # Reading 1: set baseline at 30%
        det.check(_snap(fuel_level_pct=30.0))
        # Readings 2-4: jump to 95% but still in startup window
        for _ in range(3):
            event = det.check(_snap(fuel_level_pct=95.0))
            assert event is None

    def test_evaluates_after_5_readings(self) -> None:
        """After 5 readings, fill-up detection should be active."""
        det = FillupDetector(14.8, 3.50, 31.0)
        # Burn through 4 startup readings at stable level
        for _ in range(4):
            det.check(_snap(fuel_level_pct=30.0))
        # Reading 5: still at 30%, establishes baseline post-startup
        det.check(_snap(fuel_level_pct=30.0))
        # Readings 6+: jump to 95%, confirm with multiple readings
        event = _trigger_fillup(det, 95.0)
        assert event is not None


class TestFillupDetector:

    def test_no_fillup_small_jump(self) -> None:
        det = _warmed_detector(warmup_pct=50.0)
        event = det.check(_snap(fuel_level_pct=55.0))  # only 5% jump
        assert event is None

    def test_fillup_detected_at_20pct(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 50.0)  # exactly 20%
        assert event is not None
        assert isinstance(event, FillupEvent)

    def test_fillup_gallons_calculated(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 95.0)  # 65% jump
        assert event is not None
        # 65% of 14.8 gallons = 9.62
        assert abs(event.estimated_gallons - 9.6) < 0.2

    def test_fillup_cost_calculated(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 95.0)
        assert event is not None
        assert event.cost_usd is not None
        assert event.cost_usd > 0

    def test_first_fillup_no_mpg(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 95.0)
        assert event is not None
        assert event.mpg_since_last_fill is None  # no miles_since_last_fill passed

    def test_fillup_with_mpg(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 95.0, miles_since_last_fill=280.0)
        assert event is not None
        assert event.mpg_since_last_fill is not None

    def test_full_tank_message(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 98.0)
        assert event is not None
        assert "Full tank" in event.rune_message

    def test_partial_fill_message(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 70.0)  # not full
        assert event is not None
        assert "Topped off" in event.rune_message

    def test_mpg_at_epa_qualifier(self) -> None:
        """MPG near EPA (31) should say 'right where I should be'."""
        det = _warmed_detector(warmup_pct=30.0)
        event = _trigger_fillup(det, 95.0, miles_since_last_fill=300.0)
        assert event is not None
        assert "right where I should be" in event.rune_message

    def test_mpg_above_epa_qualifier(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        # 65% of 14.8 = 9.62 gal, 400 miles / 9.62 = ~41.6 MPG -- well above 31
        event = _trigger_fillup(det, 95.0, miles_since_last_fill=400.0)
        assert event is not None
        assert "above average" in event.rune_message

    def test_mpg_below_epa_qualifier(self) -> None:
        det = _warmed_detector(warmup_pct=30.0)
        # 65% of 14.8 = 9.62 gal, 150 miles / 9.62 = ~15.6 MPG -- well below 31
        event = _trigger_fillup(det, 95.0, miles_since_last_fill=150.0)
        assert event is not None
        assert "below average" in event.rune_message

    def test_consecutive_same_level(self) -> None:
        det = _warmed_detector(warmup_pct=75.0)
        event = det.check(_snap(fuel_level_pct=75.0))
        assert event is None
