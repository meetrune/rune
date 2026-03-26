"""Tests for Rune's SQLite database layer.

Proves WAL mode, schema creation, CRUD operations, and batch writes work correctly.
Each test gets a fresh temporary database via the db fixture.
"""

from __future__ import annotations

import time

import pytest

from backend.database.db import RuneDatabase
from backend.obd_manager.models import HealthSnapshot, VehicleSnapshot


@pytest.fixture
async def db(tmp_path: object) -> RuneDatabase:  # type: ignore[override]
    """Fresh database for each test."""
    database = RuneDatabase(db_path=str(tmp_path / "test.db"))  # type: ignore[operator]
    await database.initialize()
    yield database  # type: ignore[misc]
    await database.close()


def _make_snap(**overrides: float) -> VehicleSnapshot:
    """Build a valid VehicleSnapshot with sensible defaults."""
    defaults = dict(
        rpm=700, speed_kph=0, coolant_temp_c=90, engine_load_pct=20,
        throttle_pct=0, intake_air_temp_c=25, intake_manifold_kpa=30,
        maf_gps=2.5, stft_pct=0, ltft_pct=0, fuel_level_pct=75,
        catalyst_temp_c=400, oil_temp_c=88, battery_voltage=14.2,
    )
    defaults.update(overrides)
    return VehicleSnapshot(**defaults)


def _make_health(**overrides: float) -> HealthSnapshot:
    defaults = dict(
        overall=92, engine=95, transmission=90, fuel=88,
        cooling=93, exhaust=85, electrical=94,
    )
    defaults.update(overrides)
    return HealthSnapshot(**defaults)


# --- Setup tests ---


class TestDatabaseSetup:

    async def test_wal_mode_enabled(self, db: RuneDatabase) -> None:
        conn = db._require_conn()
        cursor = await conn.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0] == "wal"

    async def test_synchronous_normal(self, db: RuneDatabase) -> None:
        conn = db._require_conn()
        cursor = await conn.execute("PRAGMA synchronous")
        row = await cursor.fetchone()
        assert row[0] == 1  # 1 = NORMAL

    async def test_tables_created(self, db: RuneDatabase) -> None:
        conn = db._require_conn()
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        assert "fillups" in tables
        assert "health_scores" in tables
        assert "sensor_readings" in tables
        assert "trips" in tables

    async def test_idempotent_init(self, db: RuneDatabase) -> None:
        await db.initialize()  # second init should not raise or duplicate


# --- Sensor readings tests ---


class TestSensorReadings:

    async def test_insert_reading(self, db: RuneDatabase) -> None:
        snap = _make_snap(rpm=2500)
        await db.insert_reading(snap)

        conn = db._require_conn()
        cursor = await conn.execute("SELECT COUNT(*) FROM sensor_readings")
        row = await cursor.fetchone()
        assert row[0] == 1

    async def test_insert_preserves_values(self, db: RuneDatabase) -> None:
        snap = _make_snap(rpm=3000, speed_kph=100, coolant_temp_c=92)
        await db.insert_reading(snap)

        conn = db._require_conn()
        cursor = await conn.execute("SELECT rpm, speed_kph, coolant_c FROM sensor_readings")
        row = await cursor.fetchone()
        assert row[0] == 3000
        assert row[1] == 100
        assert row[2] == 92

    async def test_batch_insert(self, db: RuneDatabase) -> None:
        snaps = [_make_snap(rpm=float(i * 100)) for i in range(10)]
        await db.insert_readings(snaps)

        conn = db._require_conn()
        cursor = await conn.execute("SELECT COUNT(*) FROM sensor_readings")
        row = await cursor.fetchone()
        assert row[0] == 10

    async def test_batch_insert_empty(self, db: RuneDatabase) -> None:
        await db.insert_readings([])  # should not raise


# --- Trip tests ---


class TestTrips:

    async def test_start_trip_returns_id(self, db: RuneDatabase) -> None:
        trip_id = await db.start_trip(int(time.time() * 1000))
        assert isinstance(trip_id, int)
        assert trip_id > 0

    async def test_active_trip_has_null_end(self, db: RuneDatabase) -> None:
        trip_id = await db.start_trip(int(time.time() * 1000))
        trip = await db.get_trip(trip_id)
        assert trip is not None
        assert trip["end_time"] is None

    async def test_end_trip_updates_row(self, db: RuneDatabase) -> None:
        now = int(time.time() * 1000)
        trip_id = await db.start_trip(now)
        await db.end_trip(
            trip_id=trip_id,
            end_time_ms=now + 600_000,  # 10 minutes later
            distance_miles=5.2,
            fuel_gallons=0.18,
            fuel_cost_usd=0.63,
            avg_mpg=28.9,
        )
        trip = await db.get_trip(trip_id)
        assert trip is not None
        assert trip["end_time"] == now + 600_000
        assert trip["distance_miles"] == 5.2
        assert trip["fuel_gallons"] == 0.18
        assert trip["avg_mpg"] == 28.9

    async def test_get_trip_not_found(self, db: RuneDatabase) -> None:
        assert await db.get_trip(9999) is None

    async def test_get_recent_trips_limit(self, db: RuneDatabase) -> None:
        for i in range(15):
            await db.start_trip(1000 + i)
        trips = await db.get_recent_trips(limit=10)
        assert len(trips) == 10

    async def test_recent_trips_ordered_newest_first(self, db: RuneDatabase) -> None:
        await db.start_trip(1000)
        await db.start_trip(2000)
        await db.start_trip(3000)
        trips = await db.get_recent_trips(limit=3)
        assert trips[0]["start_time"] == 3000
        assert trips[2]["start_time"] == 1000


# --- Fillup tests ---


class TestFillups:

    async def test_insert_fillup(self, db: RuneDatabase) -> None:
        await db.insert_fillup(
            detected_at_ms=int(time.time() * 1000),
            fuel_level_before=30.0,
            fuel_level_after=95.0,
            estimated_gallons=9.62,
            cost_usd=33.67,
            mpg_since_last_fill=28.4,
        )
        last = await db.get_last_fillup()
        assert last is not None
        assert last["estimated_gallons"] == 9.62
        assert last["mpg_since_last_fill"] == 28.4

    async def test_get_last_fillup_empty(self, db: RuneDatabase) -> None:
        assert await db.get_last_fillup() is None

    async def test_get_last_fillup_returns_latest(self, db: RuneDatabase) -> None:
        await db.insert_fillup(1000, 30, 90, 8.88)
        await db.insert_fillup(2000, 25, 95, 10.36)
        last = await db.get_last_fillup()
        assert last is not None
        assert last["detected_at"] == 2000
        assert last["estimated_gallons"] == 10.36


# --- Health scores tests ---


class TestHealthScores:

    async def test_insert_health_score(self, db: RuneDatabase) -> None:
        health = _make_health(overall=87)
        await db.insert_health_score(int(time.time() * 1000), health)

        conn = db._require_conn()
        cursor = await conn.execute("SELECT overall FROM health_scores")
        row = await cursor.fetchone()
        assert row[0] == 87

    async def test_get_health_trend_empty(self, db: RuneDatabase) -> None:
        trend = await db.get_health_trend(hours=24)
        assert trend == []

    async def test_get_health_trend_filters_by_hours(self, db: RuneDatabase) -> None:
        now_ms = int(time.time() * 1000)
        old_ms = now_ms - (48 * 3600 * 1000)  # 48 hours ago

        health = _make_health()
        await db.insert_health_score(old_ms, health)
        await db.insert_health_score(now_ms, health)

        trend = await db.get_health_trend(hours=24)
        assert len(trend) == 1  # only the recent one
        assert trend[0]["ts"] == now_ms


class TestCleanup:

    async def test_cleanup_removes_junk_trips(self, db: RuneDatabase) -> None:
        """Trips with < 0.01 miles should be removed by cleanup."""
        now = int(time.time() * 1000)
        # Real trip
        tid1 = await db.start_trip(now)
        await db.end_trip(tid1, now + 600000, 5.2, 0.18, 0.63, 28.9)
        # Junk trip
        tid2 = await db.start_trip(now + 1000)
        await db.end_trip(tid2, now + 2000, 0.002, 0.0001, 0.0, 0.2)

        result = await db.cleanup(retention_days=90)
        assert result["junk_trips"] == 1

        trips = await db.get_recent_trips()
        assert len(trips) == 1
        assert trips[0]["trip_id"] == tid1

    async def test_cleanup_keeps_recent_readings(self, db: RuneDatabase) -> None:
        """Readings within retention window should survive cleanup."""
        snap = _make_snap(rpm=700)
        await db.insert_reading(snap)
        result = await db.cleanup(retention_days=90)
        assert result["sensor_readings"] == 0  # nothing old to delete

        conn = db._require_conn()
        cursor = await conn.execute("SELECT COUNT(*) FROM sensor_readings")
        assert (await cursor.fetchone())[0] == 1

    async def test_db_size_bytes(self, db: RuneDatabase) -> None:
        size = await db.get_db_size_bytes()
        assert size > 0  # DB file exists and has content


class TestNotInitialized:

    def test_require_conn_raises(self) -> None:
        db = RuneDatabase()
        with pytest.raises(RuntimeError, match="not initialized"):
            db._require_conn()


class TestPurgeAll:
    """Tests for the go-live purge operation."""

    async def test_purge_empty_db(self, db: RuneDatabase) -> None:
        result = await db.purge_all()
        assert result == {
            "sensor_readings": 0, "trips": 0, "fillups": 0, "health_scores": 0,
        }

    async def test_purge_deletes_all_data(self, db: RuneDatabase) -> None:
        # Insert some data
        snap = _make_snap()
        await db.insert_reading(snap)
        await db.insert_reading(snap)
        await db.insert_reading(snap)
        trip_id = await db.start_trip(int(time.time() * 1000))
        await db.end_trip(trip_id, int(time.time() * 1000) + 60000, 5.0, 0.2, 0.68, 25.0)
        health = _make_health()
        await db.insert_health_score(int(time.time() * 1000), health)

        # Verify data exists
        counts_before = await db.get_table_counts()
        assert counts_before["sensor_readings"] == 3
        assert counts_before["trips"] == 1
        assert counts_before["health_scores"] == 1

        # Purge
        result = await db.purge_all()
        assert result["sensor_readings"] == 3
        assert result["trips"] == 1
        assert result["health_scores"] == 1

        # Verify everything is gone
        counts_after = await db.get_table_counts()
        assert counts_after["sensor_readings"] == 0
        assert counts_after["trips"] == 0
        assert counts_after["health_scores"] == 0
