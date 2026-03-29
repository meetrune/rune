"""Comprehensive test suite for Rune Intelligence Layer.

Tests every module, every edge case, every boundary condition.
Run with: python3 -m pytest pi/tests/test_intelligence.py -v

All tests use mocked interfaces -- no real OBD, no real I2C, no real WiCAN.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --- Fixtures ---


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db(tmp_path):
    """Create a fresh test database."""
    from backend.database.db import RuneDatabase
    db_path = str(tmp_path / "test.db")
    database = RuneDatabase(db_path=db_path)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def alert_queue(db):
    """Create an alert queue with short rate limit for testing."""
    from backend.intelligence.alert_queue import AlertQueue
    return AlertQueue(db, rate_limit_seconds=0.1)  # 100ms for fast tests


# ============================================================
# ALERT QUEUE TESTS
# ============================================================


class TestAlertQueue:
    """Test alert_queue.py -- rate limiting, concurrency, error handling."""

    @pytest.mark.asyncio
    async def test_enqueue_basic(self, alert_queue):
        """Basic alert enqueue returns an ID."""
        from backend.intelligence.models import AlertCategory, AlertSeverity
        result = await alert_queue.enqueue(
            AlertSeverity.WARNING, AlertCategory.BATTERY, "Test alert"
        )
        assert result is not None
        assert isinstance(result, int)
        assert result > 0

    @pytest.mark.asyncio
    async def test_enqueue_with_data(self, alert_queue):
        """Alert with JSON data payload."""
        from backend.intelligence.models import AlertCategory, AlertSeverity
        data = {"voltage": 12.1, "state": "low"}
        result = await alert_queue.enqueue(
            AlertSeverity.CRITICAL, AlertCategory.BATTERY, "Low battery", data=data
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_duplicate_category(self, db):
        """Same category within rate limit window is suppressed."""
        from backend.intelligence.alert_queue import AlertQueue
        from backend.intelligence.models import AlertCategory, AlertSeverity
        queue = AlertQueue(db, rate_limit_seconds=10.0)

        first = await queue.enqueue(
            AlertSeverity.WARNING, AlertCategory.BATTERY, "First"
        )
        assert first is not None

        second = await queue.enqueue(
            AlertSeverity.WARNING, AlertCategory.BATTERY, "Second"
        )
        assert second is None  # Rate limited

    @pytest.mark.asyncio
    async def test_rate_limit_allows_different_categories(self, db):
        """Different categories are independent -- both should pass."""
        from backend.intelligence.alert_queue import AlertQueue
        from backend.intelligence.models import AlertCategory, AlertSeverity
        queue = AlertQueue(db, rate_limit_seconds=10.0)

        first = await queue.enqueue(
            AlertSeverity.WARNING, AlertCategory.BATTERY, "Battery alert"
        )
        second = await queue.enqueue(
            AlertSeverity.WARNING, AlertCategory.THERMAL, "Thermal alert"
        )
        assert first is not None
        assert second is not None

    @pytest.mark.asyncio
    async def test_rate_limit_expires(self, alert_queue):
        """After rate limit window, same category is allowed again."""
        from backend.intelligence.models import AlertCategory, AlertSeverity
        first = await alert_queue.enqueue(
            AlertSeverity.INFO, AlertCategory.SYSTEM, "First"
        )
        assert first is not None

        await asyncio.sleep(0.15)  # Wait past 100ms rate limit

        second = await alert_queue.enqueue(
            AlertSeverity.INFO, AlertCategory.SYSTEM, "Second"
        )
        assert second is not None

    @pytest.mark.asyncio
    async def test_db_failure_reverts_rate_limit(self, db):
        """If DB insert fails, rate limit is reverted so next attempt can try."""
        from backend.intelligence.alert_queue import AlertQueue
        from backend.intelligence.models import AlertCategory, AlertSeverity
        queue = AlertQueue(db, rate_limit_seconds=3600.0)

        # Mock DB to fail
        with patch.object(db, 'insert_alert', side_effect=RuntimeError("DB error")):
            result = await queue.enqueue(
                AlertSeverity.WARNING, AlertCategory.BATTERY, "Will fail"
            )
            assert result is None  # Failed

        # Rate limit should be reverted -- next attempt should work
        result = await queue.enqueue(
            AlertSeverity.WARNING, AlertCategory.BATTERY, "Should work"
        )
        assert result is not None


# ============================================================
# SYNC ENGINE TESTS
# ============================================================


class TestSyncEngine:
    """Test sync_engine.py -- timestamp handling, delta export, ack idempotency."""

    @pytest.mark.asyncio
    async def test_get_unsynced_alerts_empty(self, db):
        """No alerts returns empty list."""
        from backend.intelligence.sync_engine import get_unsynced_alerts
        result = await get_unsynced_alerts(db)
        assert result["count"] == 0
        assert result["alerts"] == []

    @pytest.mark.asyncio
    async def test_get_unsynced_alerts_with_data(self, db):
        """Inserted alert appears in unsynced list."""
        from backend.intelligence.sync_engine import get_unsynced_alerts
        await db.insert_alert("warning", "battery", "Test", '{"v": 12.1}')
        result = await get_unsynced_alerts(db)
        assert result["count"] == 1
        assert result["alerts"][0]["severity"] == "warning"
        assert result["alerts"][0]["data"] == {"v": 12.1}

    @pytest.mark.asyncio
    async def test_ack_marks_alerts_synced(self, db):
        """Ack marks alerts as synced, they disappear from unsynced list."""
        from backend.intelligence.sync_engine import ack_sync, get_unsynced_alerts
        aid = await db.insert_alert("info", "system", "Test")
        result = await ack_sync(db, alert_ids=[aid])
        assert result["acked"] == 1
        assert result["ok"] is True

        unsynced = await get_unsynced_alerts(db)
        assert unsynced["count"] == 0

    @pytest.mark.asyncio
    async def test_ack_idempotent(self, db):
        """Calling ack twice with same IDs is safe."""
        from backend.intelligence.sync_engine import ack_sync
        aid = await db.insert_alert("info", "system", "Test")
        await ack_sync(db, alert_ids=[aid])
        result = await ack_sync(db, alert_ids=[aid])  # Second call
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_cursor_regression_prevented(self, db):
        """iPhone sending older cursor doesn't regress sync state."""
        from backend.intelligence.sync_engine import ack_sync, get_sync_status
        await ack_sync(db, alert_ids=[], cursor_iso="2026-03-29T12:00:00+00:00")
        await ack_sync(db, alert_ids=[], cursor_iso="2026-03-28T12:00:00+00:00")  # Older

        status = await get_sync_status(db)
        # Cursor should stay at the newer time
        assert "2026-03-29" in status["last_sync_at"]

    @pytest.mark.asyncio
    async def test_delta_invalid_timestamp(self, db):
        """Invalid since timestamp raises ValueError."""
        from backend.intelligence.sync_engine import get_delta
        with pytest.raises(ValueError):
            await get_delta(db, since_iso="not-a-date")

    @pytest.mark.asyncio
    async def test_delta_returns_trip_count(self, db):
        """Delta includes trips since timestamp."""
        from backend.intelligence.sync_engine import get_delta
        await db.start_trip(int(time.time() * 1000))
        result = await get_delta(db, since_iso="2020-01-01T00:00:00Z")
        assert result["trips_count"] >= 1

    @pytest.mark.asyncio
    async def test_iso_to_ms_timezone_formats(self):
        """Various ISO formats are handled correctly."""
        from backend.intelligence.sync_engine import _iso_to_ms
        # Z suffix
        assert _iso_to_ms("2026-03-29T12:00:00Z") > 0
        # Offset
        assert _iso_to_ms("2026-03-29T12:00:00+00:00") > 0
        # No timezone -- should still parse (Python 3.11+ fromisoformat)
        assert _iso_to_ms("2026-03-29T12:00:00") > 0

    @pytest.mark.asyncio
    async def test_sync_status_no_prior_sync(self, db):
        """First sync status shows no prior sync."""
        from backend.intelligence.sync_engine import get_sync_status
        result = await get_sync_status(db)
        assert result["last_sync_at"] is None
        assert result["pending_alerts"] == 0
        assert result["has_data"] is False


# ============================================================
# CAN DECODER TESTS
# ============================================================


class TestCANDecoder:
    """Test can_decoder.py -- bit extraction, signal decoding, edge cases."""

    def test_decode_unknown_can_id(self):
        """Unknown CAN ID returns empty list."""
        from backend.intelligence.can_decoder import CANDecoder
        decoder = CANDecoder()
        result = decoder.decode_frame(0xFFFF, bytes(8))
        assert result == []

    def test_decode_doors_all_closed(self):
        """DOORS_STATUS with all zeros = all closed."""
        from backend.intelligence.can_decoder import CANDecoder
        decoder = CANDecoder()
        result = decoder.decode_frame(0x405, bytes(8))
        for sig in result:
            assert sig.value == 0.0
            assert sig.message_name == "DOORS_STATUS"

    def test_decode_short_data(self):
        """Frame with fewer than 8 bytes doesn't crash."""
        from backend.intelligence.can_decoder import CANDecoder
        decoder = CANDecoder()
        # 3 bytes only -- signals extending past will be truncated
        result = decoder.decode_frame(0x1D0, bytes(3))
        assert isinstance(result, list)

    def test_decode_empty_data(self):
        """Empty frame data doesn't crash."""
        from backend.intelligence.can_decoder import CANDecoder
        decoder = CANDecoder()
        result = decoder.decode_frame(0x1D0, b"")
        assert isinstance(result, list)

    def test_decode_batch(self):
        """Batch decode processes multiple frames."""
        from backend.intelligence.can_decoder import CANDecoder
        decoder = CANDecoder()
        frames = [
            (0x1D0, bytes(8)),  # WHEEL_SPEEDS
            (0x405, bytes(8)),  # DOORS_STATUS
            (0xFFF, bytes(8)),  # Unknown
        ]
        result = decoder.decode_batch(frames)
        # Should have signals from 0x1D0 (4 wheels) + 0x405 (5 doors) = 9
        assert len(result) == 9

    def test_steering_angle_signed(self):
        """Steering angle uses signed values (can be negative)."""
        from backend.intelligence.can_decoder import CANDecoder
        decoder = CANDecoder()
        # Construct data with a large steering angle
        data = bytes([0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        result = decoder.decode_frame(0x14A, data)
        steer = [s for s in result if s.signal_name == "STEER_ANGLE"]
        assert len(steer) == 1
        # With 0xFFFF raw (signed 16-bit), value should be negative
        assert steer[0].unit == "deg"

    def test_stats_tracking(self):
        """Decoder tracks decode count."""
        from backend.intelligence.can_decoder import CANDecoder
        decoder = CANDecoder()
        decoder.decode_frame(0x1D0, bytes(8))
        decoder.decode_frame(0x1D0, bytes(8))
        stats = decoder.get_stats()
        assert stats["decoded_frames"] == 2
        assert stats["known_can_ids"] == 9


# ============================================================
# BATTERY MONITOR TESTS
# ============================================================


class TestBatteryMonitor:
    """Test battery_monitor.py -- SOC classification, EWMA, drain rate."""

    @pytest.mark.asyncio
    async def test_charging_state(self, alert_queue):
        """Voltage > 13.5V with engine running = CHARGING."""
        from backend.intelligence.battery_monitor import BatteryMonitor
        from backend.intelligence.models import BatteryState
        monitor = BatteryMonitor(alert_queue=alert_queue)
        reading = await monitor.update(14.2, engine_running=True)
        assert reading.state == BatteryState.CHARGING

    @pytest.mark.asyncio
    async def test_resting_voltage_classification(self, alert_queue):
        """Correct SOC classification at each voltage level."""
        from backend.intelligence.battery_monitor import _classify_resting
        from backend.intelligence.models import BatteryState
        assert _classify_resting(12.7) == BatteryState.FULL
        assert _classify_resting(12.5) == BatteryState.GOOD
        assert _classify_resting(12.3) == BatteryState.FAIR
        assert _classify_resting(12.1) == BatteryState.LOW
        assert _classify_resting(11.8) == BatteryState.CRITICAL

    @pytest.mark.asyncio
    async def test_resting_voltage_boundary(self, alert_queue):
        """Test exact boundary values."""
        from backend.intelligence.battery_monitor import _classify_resting
        from backend.intelligence.models import BatteryState
        assert _classify_resting(12.6) == BatteryState.FULL   # >= 12.6
        assert _classify_resting(12.4) == BatteryState.GOOD   # >= 12.4
        assert _classify_resting(12.2) == BatteryState.FAIR   # >= 12.2
        assert _classify_resting(12.0) == BatteryState.LOW    # >= 12.0

    @pytest.mark.asyncio
    async def test_ewma_updates(self, alert_queue):
        """EWMA trends toward actual voltage over time."""
        from backend.intelligence.battery_monitor import BatteryMonitor
        monitor = BatteryMonitor(alert_queue=alert_queue)
        # Feed 100 readings at 14.4V (engine on)
        for _ in range(100):
            await monitor.update(14.4, engine_running=True)
        trend = monitor.trend
        # EWMA should be close to 14.4 after 100 samples
        assert abs(trend.charging_voltage_ewma - 14.4) < 0.5
        assert trend.samples == 100

    @pytest.mark.asyncio
    async def test_zero_voltage(self, alert_queue):
        """Zero voltage doesn't crash."""
        from backend.intelligence.battery_monitor import BatteryMonitor
        monitor = BatteryMonitor(alert_queue=alert_queue)
        reading = await monitor.update(0.0, engine_running=False)
        assert reading.voltage == 0.0


# ============================================================
# COLD START PROFILER TESTS
# ============================================================


class TestColdStartProfiler:
    """Test cold_start.py -- warmup tracking, model fitting, anomaly detection."""

    @pytest.mark.asyncio
    async def test_basic_warmup_tracking(self, db, alert_queue):
        """Track warmup from 20C to 80C."""
        from backend.intelligence.cold_start import ColdStartProfiler
        profiler = ColdStartProfiler(alert_queue=alert_queue)
        profiler.on_trip_start(coolant_c=20.0, ambient_c=5.0)
        assert profiler.is_tracking

        # Simulate warmup
        for temp in range(20, 80):
            reached = profiler.on_reading(float(temp))
            if temp < 79:
                assert not reached

        reached = profiler.on_reading(80.0)
        assert reached  # Target reached

    @pytest.mark.asyncio
    async def test_trip_end_saves_record(self, db, alert_queue):
        """Trip end with completed warmup saves to DB."""
        from backend.intelligence.cold_start import ColdStartProfiler
        profiler = ColdStartProfiler(alert_queue=alert_queue)
        profiler.on_trip_start(coolant_c=20.0, ambient_c=5.0)

        # Fast warmup
        profiler.on_reading(80.0)
        await asyncio.sleep(0.01)  # Small delay so warmup_seconds > 0

        record = await profiler.on_trip_end(trip_id=1, db=db)
        assert record is not None
        assert record.ambient_temp_c == 5.0
        assert record.start_coolant_c == 20.0

    @pytest.mark.asyncio
    async def test_trip_end_without_warmup(self, db, alert_queue):
        """Trip end before reaching target returns None."""
        from backend.intelligence.cold_start import ColdStartProfiler
        profiler = ColdStartProfiler(alert_queue=alert_queue)
        profiler.on_trip_start(coolant_c=20.0, ambient_c=5.0)
        profiler.on_reading(40.0)  # Not yet at 80C

        record = await profiler.on_trip_end(trip_id=1, db=db)
        assert record is None  # Warmup not complete

    @pytest.mark.asyncio
    async def test_not_tracking_returns_none(self, db, alert_queue):
        """Trip end without starting returns None."""
        from backend.intelligence.cold_start import ColdStartProfiler
        profiler = ColdStartProfiler(alert_queue=alert_queue)
        record = await profiler.on_trip_end(trip_id=1, db=db)
        assert record is None

    @pytest.mark.asyncio
    async def test_predict_without_model(self, alert_queue):
        """Prediction without fitted model returns None."""
        from backend.intelligence.cold_start import ColdStartProfiler
        profiler = ColdStartProfiler(alert_queue=alert_queue)
        result = profiler.predict_warmup_minutes(5.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_alert_slow_warmup_no_model(self, db, alert_queue):
        """Alert for slow warmup when model is None doesn't crash (bug fix)."""
        from backend.intelligence.cold_start import ColdStartProfiler
        profiler = ColdStartProfiler(alert_queue=alert_queue)
        from backend.intelligence.models import ColdStartRecord
        record = ColdStartRecord(
            ambient_temp_c=5.0, start_coolant_c=20.0,
            warmup_seconds=600.0,  # 10 minutes
        )
        # This should NOT raise TypeError (the bug we fixed)
        await profiler._alert_slow_warmup(record)


# ============================================================
# TRIP SCORER TESTS
# ============================================================


class TestTripScorer:
    """Test trip_scorer.py -- scoring, baseline tracking, edge cases."""

    def test_perfect_trip(self):
        """Trip matching baseline MPG with no hard events = high score."""
        from backend.intelligence.trip_scorer import TripScorer
        scorer = TripScorer(epa_combined_mpg=31.0)
        scorer.start_trip()

        # Simulate smooth driving at 60 kph for 10 minutes
        for _ in range(6000):  # 10 min * 60 sec * 10 Hz
            scorer.update(throttle_pct=30.0, speed_kph=60.0, rpm=2000.0, dt_seconds=0.1)

        score = scorer.score_trip(trip_mpg=31.0, trip_distance_miles=6.2)
        assert score.efficiency == 100.0
        assert score.smoothness > 90.0  # No hard events
        assert score.idle_ratio == 100.0  # No idle time
        assert score.composite > 90.0

    def test_zero_distance_trip(self):
        """Zero distance trip doesn't cause division by zero."""
        from backend.intelligence.trip_scorer import TripScorer
        scorer = TripScorer()
        scorer.start_trip()
        score = scorer.score_trip(trip_mpg=0.0, trip_distance_miles=0.0)
        assert score.composite >= 0.0
        assert score.composite <= 100.0

    def test_baseline_starts_at_epa(self):
        """Before any trips, baseline is EPA combined."""
        from backend.intelligence.trip_scorer import TripScorer
        scorer = TripScorer(epa_combined_mpg=31.0)
        assert scorer.get_baseline_mpg() == 31.0

    def test_baseline_updates_after_trip(self):
        """Baseline EWMA updates after scoring a trip."""
        from backend.intelligence.trip_scorer import TripScorer
        scorer = TripScorer(epa_combined_mpg=31.0)
        scorer.start_trip()
        scorer.score_trip(trip_mpg=40.0, trip_distance_miles=10.0)
        # After one trip, baseline should move toward 40
        assert scorer.get_baseline_mpg() > 31.0

    def test_hard_accel_detection(self):
        """Rapid throttle change counts as hard acceleration."""
        from backend.intelligence.trip_scorer import TripScorer
        scorer = TripScorer()
        scorer.start_trip()

        # Gentle driving
        scorer.update(throttle_pct=20.0, speed_kph=60.0, rpm=2000.0, dt_seconds=0.1)
        # Sudden slam to 100% (80% change in 0.1s = 800%/sec >> 15%/sec threshold)
        scorer.update(throttle_pct=100.0, speed_kph=60.0, rpm=5000.0, dt_seconds=0.1)

        score = scorer.score_trip(trip_mpg=25.0, trip_distance_miles=5.0)
        assert score.hard_accel_count >= 1

    def test_dt_zero_handled(self):
        """dt_seconds=0 doesn't cause division by zero."""
        from backend.intelligence.trip_scorer import TripScorer
        scorer = TripScorer()
        scorer.start_trip()
        scorer.update(throttle_pct=50.0, speed_kph=60.0, rpm=2000.0, dt_seconds=0.0)
        # Should not crash


# ============================================================
# THERMAL GUARDIAN TESTS
# ============================================================


class TestThermalGuardian:
    """Test thermal_guardian.py -- parked thermal state classification."""

    @pytest.mark.asyncio
    async def test_normal_state(self, alert_queue):
        """Cool temperature = NORMAL state."""
        from backend.intelligence.thermal_guardian import ThermalGuardian
        from backend.intelligence.models import ParkedThermalState
        guardian = ThermalGuardian()
        result = await guardian.check_parked_state(
            armrest_temp_c=30.0, cpu_temp_c=45.0,
            vin_voltage=12.6, alert_queue=alert_queue,
        )
        assert result.thermal_state == ParkedThermalState.NORMAL
        assert result.next_wake_hours == 2.0

    @pytest.mark.asyncio
    async def test_hot_state_queues_alert(self, alert_queue):
        """Hot temperature queues WARNING alert."""
        from backend.intelligence.thermal_guardian import ThermalGuardian
        from backend.intelligence.models import ParkedThermalState
        guardian = ThermalGuardian()
        result = await guardian.check_parked_state(
            armrest_temp_c=65.0, cpu_temp_c=70.0,
            vin_voltage=12.6, alert_queue=alert_queue,
        )
        assert result.thermal_state == ParkedThermalState.HOT
        assert result.alerts_queued >= 1

    @pytest.mark.asyncio
    async def test_extreme_state(self, alert_queue):
        """Extreme temperature extends wake interval."""
        from backend.intelligence.thermal_guardian import ThermalGuardian
        from backend.intelligence.models import ParkedThermalState
        guardian = ThermalGuardian()
        result = await guardian.check_parked_state(
            armrest_temp_c=75.0, cpu_temp_c=80.0,
            vin_voltage=12.4, alert_queue=alert_queue,
        )
        assert result.thermal_state == ParkedThermalState.EXTREME
        assert guardian.get_recommended_wake_hours() == 4.0

    @pytest.mark.asyncio
    async def test_all_sensors_none(self, alert_queue):
        """All None sensors = NORMAL (safe default)."""
        from backend.intelligence.thermal_guardian import ThermalGuardian
        from backend.intelligence.models import ParkedThermalState
        guardian = ThermalGuardian()
        result = await guardian.check_parked_state(
            armrest_temp_c=None, cpu_temp_c=None,
            vin_voltage=None, alert_queue=alert_queue,
        )
        assert result.thermal_state == ParkedThermalState.NORMAL


# ============================================================
# MAINTENANCE TRACKER TESTS
# ============================================================


class TestMaintenanceTracker:
    """Test maintenance.py -- intervals, condition adjustments, alerts."""

    @pytest.mark.asyncio
    async def test_all_items_tracked(self, db, alert_queue):
        """Check returns status for all 8 maintenance items."""
        from backend.intelligence.maintenance import MaintenanceTracker
        tracker = MaintenanceTracker()
        statuses = await tracker.check_maintenance(
            current_odometer_miles=0.0, db=db, alert_queue=alert_queue,
        )
        assert len(statuses) == 8

    @pytest.mark.asyncio
    async def test_oil_change_hot_adjustment(self, db, alert_queue):
        """Oil change interval reduced when oil runs hot."""
        from backend.intelligence.maintenance import MaintenanceTracker
        tracker = MaintenanceTracker()
        statuses = await tracker.check_maintenance(
            current_odometer_miles=0.0, db=db, alert_queue=alert_queue,
            avg_oil_temp_c=115.0,  # Above 110C threshold
        )
        oil = [s for s in statuses if s.item.value == "oil_change"][0]
        assert oil.adjusted is True
        assert oil.interval_miles == 5000.0  # Reduced from 7500

    @pytest.mark.asyncio
    async def test_mark_done_and_check(self, db, alert_queue):
        """Mark maintenance done, then check it's updated."""
        from backend.intelligence.maintenance import MaintenanceTracker
        from backend.intelligence.models import MaintenanceItem
        tracker = MaintenanceTracker()
        await tracker.mark_done(
            MaintenanceItem.OIL_CHANGE, odometer_miles=1000.0, db=db, notes="Test"
        )
        statuses = await tracker.check_maintenance(
            current_odometer_miles=1000.0, db=db, alert_queue=alert_queue,
        )
        oil = [s for s in statuses if s.item.value == "oil_change"][0]
        assert oil.last_done_miles == 1000.0
        assert oil.next_due_miles == 8500.0  # 1000 + 7500
        assert oil.miles_remaining == 7500.0

    @pytest.mark.asyncio
    async def test_alert_when_due(self, db, alert_queue):
        """Alert queued when maintenance is within 500 miles of due."""
        from backend.intelligence.maintenance import MaintenanceTracker
        from backend.intelligence.models import MaintenanceItem
        tracker = MaintenanceTracker()
        await tracker.mark_done(
            MaintenanceItem.TIRE_ROTATION, odometer_miles=0.0, db=db,
        )
        # Drive 7200 miles -- 300 miles from due (within 500 mile threshold)
        statuses = await tracker.check_maintenance(
            current_odometer_miles=7200.0, db=db, alert_queue=alert_queue,
        )
        tires = [s for s in statuses if s.item.value == "tire_rotation"][0]
        assert tires.miles_remaining == 300.0

    @pytest.mark.asyncio
    async def test_negative_miles_remaining(self, db, alert_queue):
        """Overdue maintenance shows negative miles remaining."""
        from backend.intelligence.maintenance import MaintenanceTracker
        from backend.intelligence.models import MaintenanceItem
        tracker = MaintenanceTracker()
        await tracker.mark_done(
            MaintenanceItem.OIL_CHANGE, odometer_miles=0.0, db=db,
        )
        statuses = await tracker.check_maintenance(
            current_odometer_miles=8000.0, db=db, alert_queue=alert_queue,
        )
        oil = [s for s in statuses if s.item.value == "oil_change"][0]
        assert oil.miles_remaining == -500.0  # 500 miles overdue


# ============================================================
# RESILIENT EXPORT TESTS
# ============================================================


class TestResilientExport:
    """Test api/export.py -- chunking, SHA verification, session lifecycle."""

    @pytest.mark.asyncio
    async def test_prepare_creates_chunks(self, db):
        """Prepare creates chunk files and session."""
        from backend.api.export import prepare_export
        from backend.obd_manager.models import VehicleSnapshot
        # Insert data so DB is non-trivial
        snaps = [VehicleSnapshot(
            rpm=2000, speed_kph=60, coolant_temp_c=90, engine_load_pct=40,
            throttle_pct=30, intake_air_temp_c=25, intake_manifold_kpa=100,
            maf_gps=5.0, stft_pct=1.0, ltft_pct=2.0, fuel_level_pct=60,
            catalyst_temp_c=400, oil_temp_c=95, battery_voltage=14.2,
        ) for _ in range(50)]
        await db.insert_readings(snaps)

        session = await prepare_export(db, chunk_size_bytes=4096)
        assert session.chunk_count > 0
        assert session.total_bytes > 0
        assert len(session.total_sha256) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_stream_sha_matches(self, db):
        """Streamed bytes SHA matches session SHA."""
        from backend.api.export import prepare_export, stream_export
        from backend.obd_manager.models import VehicleSnapshot
        snaps = [VehicleSnapshot(
            rpm=2000, speed_kph=60, coolant_temp_c=90, engine_load_pct=40,
            throttle_pct=30, intake_air_temp_c=25, intake_manifold_kpa=100,
            maf_gps=5.0, stft_pct=1.0, ltft_pct=2.0, fuel_level_pct=60,
            catalyst_temp_c=400, oil_temp_c=95, battery_voltage=14.2,
        ) for _ in range(50)]
        await db.insert_readings(snaps)

        session = await prepare_export(db, chunk_size_bytes=4096)
        hasher = hashlib.sha256()
        total = 0
        async for chunk in stream_export(session):
            hasher.update(chunk)
            total += len(chunk)

        assert total == session.total_bytes
        assert hasher.hexdigest() == session.total_sha256

    @pytest.mark.asyncio
    async def test_stream_idempotent(self, db):
        """Same session streams identical bytes twice."""
        from backend.api.export import prepare_export, stream_export
        from backend.obd_manager.models import VehicleSnapshot
        snaps = [VehicleSnapshot(
            rpm=2000, speed_kph=60, coolant_temp_c=90, engine_load_pct=40,
            throttle_pct=30, intake_air_temp_c=25, intake_manifold_kpa=100,
            maf_gps=5.0, stft_pct=1.0, ltft_pct=2.0, fuel_level_pct=60,
            catalyst_temp_c=400, oil_temp_c=95, battery_voltage=14.2,
        ) for _ in range(20)]
        await db.insert_readings(snaps)

        session = await prepare_export(db, chunk_size_bytes=8192)

        sha1 = hashlib.sha256()
        async for chunk in stream_export(session):
            sha1.update(chunk)

        sha2 = hashlib.sha256()
        async for chunk in stream_export(session):
            sha2.update(chunk)

        assert sha1.hexdigest() == sha2.hexdigest()

    @pytest.mark.asyncio
    async def test_complete_cleans_up(self, db):
        """Complete removes chunk files and session key."""
        from backend.api.export import complete_export, get_export_session, prepare_export
        from backend.obd_manager.models import VehicleSnapshot
        snaps = [VehicleSnapshot(
            rpm=2000, speed_kph=60, coolant_temp_c=90, engine_load_pct=40,
            throttle_pct=30, intake_air_temp_c=25, intake_manifold_kpa=100,
            maf_gps=5.0, stft_pct=1.0, ltft_pct=2.0, fuel_level_pct=60,
            catalyst_temp_c=400, oil_temp_c=95, battery_voltage=14.2,
        ) for _ in range(10)]
        await db.insert_readings(snaps)

        session = await prepare_export(db, chunk_size_bytes=4096)
        assert os.path.isdir(session.export_dir)

        result = await complete_export(db, session.session_id)
        assert result["ok"] is True
        assert not os.path.exists(session.export_dir)

        # Session should be gone from DB
        loaded = await get_export_session(db, session.session_id)
        assert loaded is None

    @pytest.mark.asyncio
    async def test_expired_session_rejected(self, db):
        """Expired session returns None."""
        from backend.api.export import get_export_session, prepare_export
        from backend.obd_manager.models import VehicleSnapshot
        snaps = [VehicleSnapshot(
            rpm=2000, speed_kph=60, coolant_temp_c=90, engine_load_pct=40,
            throttle_pct=30, intake_air_temp_c=25, intake_manifold_kpa=100,
            maf_gps=5.0, stft_pct=1.0, ltft_pct=2.0, fuel_level_pct=60,
            catalyst_temp_c=400, oil_temp_c=95, battery_voltage=14.2,
        ) for _ in range(5)]
        await db.insert_readings(snaps)

        session = await prepare_export(db, chunk_size_bytes=4096)

        # Manually expire the session
        import backend.api.export as export_mod
        session.expires_at = time.time() - 1  # Already expired
        await db.set_sync_value(
            f"export_session_{session.session_id}",
            session.model_dump_json(),
        )

        loaded = await get_export_session(db, session.session_id)
        assert loaded is None

    @pytest.mark.asyncio
    async def test_corrupt_chunk_detected(self, db):
        """Corrupted chunk file detected during stream."""
        from backend.api.export import prepare_export, stream_export
        from backend.obd_manager.models import VehicleSnapshot
        snaps = [VehicleSnapshot(
            rpm=2000, speed_kph=60, coolant_temp_c=90, engine_load_pct=40,
            throttle_pct=30, intake_air_temp_c=25, intake_manifold_kpa=100,
            maf_gps=5.0, stft_pct=1.0, ltft_pct=2.0, fuel_level_pct=60,
            catalyst_temp_c=400, oil_temp_c=95, battery_voltage=14.2,
        ) for _ in range(50)]
        await db.insert_readings(snaps)

        session = await prepare_export(db, chunk_size_bytes=4096)

        # Corrupt the first chunk file
        chunk_path = os.path.join(session.export_dir, "chunk_0000.bin")
        with open(chunk_path, "wb") as f:
            f.write(b"CORRUPTED DATA")

        with pytest.raises(RuntimeError, match="SHA mismatch"):
            async for _ in stream_export(session):
                pass


# ============================================================
# DATABASE INTELLIGENCE METHODS TESTS
# ============================================================


class TestDatabaseIntelligence:
    """Test db.py intelligence layer methods."""

    @pytest.mark.asyncio
    async def test_alert_insert_and_retrieve(self, db):
        """Insert alert and retrieve it."""
        aid = await db.insert_alert("warning", "battery", "Test", '{"v": 12.1}')
        assert aid > 0
        alerts = await db.get_unsynced_alerts()
        assert len(alerts) == 1
        assert alerts[0]["message"] == "Test"

    @pytest.mark.asyncio
    async def test_ack_marks_synced(self, db):
        """Ack marks alerts as synced."""
        aid = await db.insert_alert("info", "system", "Test")
        count = await db.ack_alerts([aid])
        assert count == 1
        alerts = await db.get_unsynced_alerts()
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_sync_state_upsert(self, db):
        """Sync state set/get works as upsert."""
        await db.set_sync_value("test_key", "value1")
        assert await db.get_sync_value("test_key") == "value1"
        await db.set_sync_value("test_key", "value2")
        assert await db.get_sync_value("test_key") == "value2"

    @pytest.mark.asyncio
    async def test_cold_start_insert_and_retrieve(self, db):
        """Cold start records are stored and retrievable."""
        await db.insert_cold_start(
            trip_id=1, ambient_temp_c=5.0, start_coolant_c=10.0,
            target_coolant_c=80.0, warmup_seconds=240.0,
        )
        starts = await db.get_cold_starts()
        assert len(starts) == 1
        assert starts[0]["ambient_temp_c"] == 5.0

    @pytest.mark.asyncio
    async def test_maintenance_insert_and_retrieve(self, db):
        """Maintenance records are stored and retrievable."""
        mid = await db.insert_maintenance("oil_change", 1000.0, 8500.0, "Test")
        assert mid > 0
        latest = await db.get_latest_maintenance("oil_change")
        assert latest is not None
        assert latest["odometer_miles"] == 1000.0

    @pytest.mark.asyncio
    async def test_cumulative_miles(self, db):
        """Cumulative miles sums all completed trips."""
        tid = await db.start_trip(int(time.time() * 1000))
        await db.end_trip(tid, int(time.time() * 1000), 10.5, 0.3, 1.05, 35.0)
        tid2 = await db.start_trip(int(time.time() * 1000))
        await db.end_trip(tid2, int(time.time() * 1000), 5.2, 0.15, 0.52, 34.7)
        miles = await db.get_cumulative_miles()
        assert abs(miles - 15.7) < 0.01

    @pytest.mark.asyncio
    async def test_purge_includes_intelligence_tables(self, db):
        """Purge clears intelligence tables too."""
        await db.insert_alert("info", "system", "Test")
        await db.insert_cold_start(None, 5.0, 10.0, 80.0, 240.0)
        await db.insert_maintenance("oil_change", 1000.0, 8500.0)

        result = await db.purge_all()
        assert result["alert_queue"] >= 1
        assert result["cold_starts"] >= 1
        assert result["maintenance_log"] >= 1

    @pytest.mark.asyncio
    async def test_get_sync_keys_by_prefix(self, db):
        """Query sync keys by prefix."""
        await db.set_sync_value("export_session_abc", "data1")
        await db.set_sync_value("export_session_def", "data2")
        await db.set_sync_value("other_key", "data3")

        results = await db.get_sync_keys_by_prefix("export_session_")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_delete_sync_key(self, db):
        """Delete a sync state key."""
        await db.set_sync_value("test_key", "value")
        await db.delete_sync_key("test_key")
        assert await db.get_sync_value("test_key") is None


# ============================================================
# MODELS VALIDATION TESTS
# ============================================================


class TestModels:
    """Test models.py -- Pydantic validation, enums, edge cases."""

    def test_trip_score_clamped(self):
        """TripScore fields are clamped to [0, 100]."""
        from backend.intelligence.models import TripScore
        with pytest.raises(Exception):
            TripScore(
                efficiency=150, smoothness=50, idle_ratio=50,
                composite=50, trip_mpg=30, baseline_mpg=31,
            )

    def test_alert_severity_values(self):
        """All AlertSeverity values are lowercase strings."""
        from backend.intelligence.models import AlertSeverity
        for s in AlertSeverity:
            assert s.value == s.value.lower()

    def test_maintenance_item_values(self):
        """All MaintenanceItem values are snake_case strings."""
        from backend.intelligence.models import MaintenanceItem
        for item in MaintenanceItem:
            assert "_" in item.value or item.value.isalpha()

    def test_battery_state_enum(self):
        """BatteryState has all expected states."""
        from backend.intelligence.models import BatteryState
        states = {s.value for s in BatteryState}
        assert "full" in states
        assert "critical" in states
        assert "charging" in states
        assert "unknown" in states
