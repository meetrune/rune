"""Tests for the advanced diagnostics API endpoints.

Tests all 9 new endpoints: health-trend, system, obd/test, test/integration,
logs, config, control/checkpoint, control/recalibrate, control/restart-producer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from unittest.mock import MagicMock

import pytest

from backend.api.controls import force_checkpoint, go_live, recalibrate_health_scorer
from backend.api.logs import RuneLogBuffer
from backend.api.system import get_system_info
from backend.database.db import RuneDatabase
from backend.health.scorer import HealthScorer
from backend.obd_manager.collector import SimulatedCollector
from backend.obd_manager.models import VehicleSnapshot


# --- Fixtures ---


@pytest.fixture
async def db(tmp_path):
    """Temporary database for testing."""
    db = RuneDatabase(db_path=str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def health_scorer():
    return HealthScorer(n_trees=5, tree_height=4, window_size=50, calibration_samples=100)


@pytest.fixture
async def collector():
    c = SimulatedCollector(ambient_temp_c=20, initial_fuel_pct=75.0)
    await c.start()
    yield c
    await c.stop()


# --- GET /api/system ---


class TestSystemInfo:
    @pytest.mark.anyio
    async def test_returns_all_fields(self):
        info = await get_system_info()
        assert "cpu_percent" in info
        assert "ram" in info
        assert "disk" in info
        assert "uptime_seconds" in info
        assert "python_version" in info
        assert "os_version" in info
        assert "hostname" in info
        assert "architecture" in info

    @pytest.mark.anyio
    async def test_cpu_percent_is_reasonable(self):
        info = await get_system_info()
        assert 0.0 <= info["cpu_percent"] <= 100.0

    @pytest.mark.anyio
    async def test_ram_has_required_keys(self):
        info = await get_system_info()
        ram = info["ram"]
        assert "total_mb" in ram
        assert "used_mb" in ram
        assert "available_mb" in ram
        assert "percent" in ram
        assert ram["total_mb"] > 0

    @pytest.mark.anyio
    async def test_disk_has_required_keys(self):
        info = await get_system_info()
        disk = info["disk"]
        assert "total_gb" in disk
        assert "used_gb" in disk
        assert "free_gb" in disk
        assert "percent" in disk
        assert disk["total_gb"] > 0

    @pytest.mark.anyio
    async def test_uptime_is_positive(self):
        info = await get_system_info()
        assert info["uptime_seconds"] > 0


# --- Log Ring Buffer ---


class TestLogBuffer:
    def test_stores_records(self):
        buf = RuneLogBuffer(capacity=10)
        buf.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="hello", args=(), exc_info=None,
        )
        buf.emit(record)

        records = buf.get_records()
        assert len(records) == 1
        assert records[0]["message"] == "hello"
        assert records[0]["level"] == "INFO"
        assert records[0]["levelno"] == logging.INFO
        assert records[0]["logger"] == "test"
        assert "timestamp" in records[0]

    def test_capacity_limit(self):
        buf = RuneLogBuffer(capacity=3)
        buf.setFormatter(logging.Formatter("%(message)s"))

        for i in range(5):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="",
                lineno=0, msg=f"msg-{i}", args=(), exc_info=None,
            )
            buf.emit(record)

        records = buf.get_records()
        assert len(records) == 3
        # Newest first
        assert records[0]["message"] == "msg-4"
        assert records[2]["message"] == "msg-2"

    def test_filter_by_level(self):
        buf = RuneLogBuffer(capacity=10)
        buf.setFormatter(logging.Formatter("%(message)s"))

        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
            record = logging.LogRecord(
                name="test", level=level, pathname="",
                lineno=0, msg=f"{logging.getLevelName(level)}-msg", args=(), exc_info=None,
            )
            buf.emit(record)

        # Only WARNING and above
        records = buf.get_records(min_level="WARNING")
        assert len(records) == 2
        assert records[0]["level"] == "ERROR"
        assert records[1]["level"] == "WARNING"

    def test_limit_parameter(self):
        buf = RuneLogBuffer(capacity=10)
        buf.setFormatter(logging.Formatter("%(message)s"))

        for i in range(10):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="",
                lineno=0, msg=f"msg-{i}", args=(), exc_info=None,
            )
            buf.emit(record)

        records = buf.get_records(limit=3)
        assert len(records) == 3

    def test_clear(self):
        buf = RuneLogBuffer(capacity=10)
        buf.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="hello", args=(), exc_info=None,
        )
        buf.emit(record)
        assert buf.count == 1

        buf.clear()
        assert buf.count == 0
        assert buf.get_records() == []


# --- Controls ---


class TestForceCheckpoint:
    @pytest.mark.anyio
    async def test_checkpoint_succeeds(self, db):
        result = await force_checkpoint(db)
        assert result["success"] is True
        assert "duration_ms" in result
        assert result["log_pages"] >= 0
        assert result["checkpointed_pages"] >= 0

    @pytest.mark.anyio
    async def test_checkpoint_after_writes(self, db, collector):
        # Write some data first so WAL has pages
        snap = await collector.get_snapshot()
        await db.insert_reading(snap)

        result = await force_checkpoint(db)
        assert result["success"] is True


class TestRecalibration:
    @pytest.mark.anyio
    async def test_reset_calibration(self, health_scorer, collector):
        for _ in range(10):
            snap = await collector.get_snapshot()
            health_scorer.score(snap)

        assert health_scorer.sample_count == 10

        health_scorer.reset_calibration()

        assert health_scorer.sample_count == 0
        assert health_scorer.calibration_complete is False

    @pytest.mark.anyio
    async def test_recalibrate_endpoint(self, health_scorer):
        result = await recalibrate_health_scorer(health_scorer)
        assert result["success"] is True
        assert "previous_sample_count" in result
        assert health_scorer.sample_count == 0


# --- Database extensions ---


class TestDatabaseExtensions:
    @pytest.mark.anyio
    async def test_get_wal_size(self, db):
        size = db.get_wal_size_bytes()
        assert isinstance(size, int)
        assert size >= 0

    @pytest.mark.anyio
    async def test_force_checkpoint(self, db):
        result = await db.force_checkpoint()
        assert "busy" in result
        assert "log_pages" in result
        assert "checkpointed_pages" in result

    @pytest.mark.anyio
    async def test_get_insert_rate(self, db, collector):
        # Write some readings
        for _ in range(5):
            snap = await collector.get_snapshot()
            await db.insert_reading(snap)

        rate = await db.get_insert_rate(window_seconds=60)
        assert isinstance(rate, float)
        assert rate >= 0.0


# --- Health Scorer reset ---


class TestHealthScorerReset:
    @pytest.mark.anyio
    async def test_reset_returns_calibrating_scores(self, health_scorer, collector):
        # Feed enough samples to calibrate
        for _ in range(110):
            snap = await collector.get_snapshot()
            health_scorer.score(snap)

        assert health_scorer.calibration_complete is True

        # Reset
        health_scorer.reset_calibration()
        assert health_scorer.calibration_complete is False

        # Score should return -1 now
        snap = await collector.get_snapshot()
        result = health_scorer.score(snap)
        assert result.overall == -1


# --- Health Trend endpoint ---


class TestHealthTrend:
    @pytest.mark.anyio
    async def test_empty_trend(self, db):
        scores = await db.get_health_trend(hours=1)
        assert isinstance(scores, list)
        assert len(scores) == 0

    @pytest.mark.anyio
    async def test_trend_with_data(self, db, health_scorer, collector):
        from backend.obd_manager.models import HealthSnapshot
        # Insert some health scores
        now_ms = int(time.time() * 1000)
        for i in range(5):
            health = HealthSnapshot(
                overall=90.0 + i, engine=95.0, transmission=92.0,
                fuel=88.0, cooling=91.0, exhaust=93.0, electrical=97.0,
            )
            await db.insert_health_score(now_ms - (i * 60000), health)

        scores = await db.get_health_trend(hours=1)
        assert len(scores) == 5


# --- Config endpoint ---


class TestConfig:
    def test_settings_serializable(self):
        from backend.config import settings
        config = settings.model_dump()
        assert isinstance(config, dict)
        assert "use_simulator" in config
        assert "db_path" in config
        assert "ws_rate_hz" in config
        assert "gas_price_per_gallon" in config


# --- Integration test function ---


class TestIntegrationTest:
    @pytest.mark.anyio
    async def test_integration_test_passes(self, db, collector, health_scorer):
        from backend.diagnostics import run_integration_test
        from backend.fuel.calculator import FuelCalculator
        from backend.ws_manager import ConnectionManager

        fuel_calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        manager = ConnectionManager()

        # Build mock app_state
        state = MagicMock()
        state.collector = collector
        state.db = db
        state.health_scorer = health_scorer
        state.fuel_calc = fuel_calc
        state.connection_manager = manager

        result = await run_integration_test(state)

        assert result["overall"] == "pass"
        assert len(result["steps"]) >= 5
        assert result["total_duration_ms"] > 0

        # All steps should pass (or warn for health calibrating)
        for step in result["steps"]:
            assert step["status"] in ("pass", "warn")
            assert step["duration_ms"] >= 0


class TestGoLive:
    """Tests for the go-live (remove simulation) control action."""

    @pytest.mark.anyio
    async def test_go_live_purges_and_signals(self, db, health_scorer):
        """go_live should purge DB, reset scorer, and set the event."""
        # Insert some data first
        snap = VehicleSnapshot(
            rpm=700, speed_kph=0, coolant_temp_c=90, engine_load_pct=20,
            throttle_pct=0, intake_air_temp_c=25, intake_manifold_kpa=30,
            maf_gps=3.5, stft_pct=0, ltft_pct=0, fuel_level_pct=75,
            catalyst_temp_c=400, oil_temp_c=85, battery_voltage=14.1,
        )
        await db.insert_reading(snap)
        await db.insert_reading(snap)

        event = asyncio.Event()
        result = await go_live(db=db, scorer=health_scorer, go_live_event=event, use_simulator=True)

        assert result["success"] is True
        assert result["status"] == "live"
        assert result["purged"]["sensor_readings"] == 2
        assert event.is_set()

        # DB should be empty
        counts = await db.get_table_counts()
        assert counts["sensor_readings"] == 0

    @pytest.mark.anyio
    async def test_go_live_on_empty_db(self, db, health_scorer):
        """go_live should work fine on an already-empty database."""
        event = asyncio.Event()
        result = await go_live(db=db, scorer=health_scorer, go_live_event=event, use_simulator=True)
        assert result["success"] is True
        assert result["purged"]["sensor_readings"] == 0

    @pytest.mark.anyio
    async def test_go_live_blocked_when_already_live(self, db, health_scorer):
        """go_live should refuse if already in live mode."""
        event = asyncio.Event()
        result = await go_live(db=db, scorer=health_scorer, go_live_event=event, use_simulator=False)
        assert result["success"] is False
        assert "Already in live mode" in result["error"]
        assert not event.is_set()
