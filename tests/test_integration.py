"""Integration tests for the producer loop wiring.

Tests the full pipeline: OBD snapshot -> FuelCalculator -> HealthScorer ->
WebSocket broadcast -> DB writes. Verifies that components work together,
not just individually.

These are the "test the wiring" tests called out in CLAUDE.md.
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock

import pytest

from backend.database.db import RuneDatabase
from backend.fuel.calculator import FuelCalculator
from backend.fuel.fillup import FillupDetector
from backend.fuel.trip_stats import TripStatsAccumulator
from backend.health.scorer import HealthScorer
from backend.obd_manager.collector import SimulatedCollector
from backend.obd_manager.models import WebSocketMessage
from backend.ws_manager import ConnectionManager


@pytest.fixture
async def db(tmp_path):
    """Create a temporary database for testing."""
    db = RuneDatabase(db_path=str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def fuel_calc():
    return FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)


@pytest.fixture
def fillup_detector():
    return FillupDetector(
        tank_capacity_gal=14.8,
        gas_price_per_gallon=3.50,
        epa_combined_mpg=31.0,
    )


@pytest.fixture
def health_scorer():
    return HealthScorer(n_trees=5, tree_height=4, window_size=50, calibration_samples=100)


@pytest.fixture
def collector():
    c = SimulatedCollector(ambient_temp_c=20, initial_fuel_pct=75.0)
    return c


class TestProducerLoopWiring:
    """Tests that simulate what obd_producer_loop does: get snapshot, process, broadcast, persist."""

    async def test_snapshot_to_websocket_message(self, collector):
        """Snapshot -> FuelCalc -> HealthScorer -> WebSocketMessage has all expected fields."""
        await collector.start()
        snap = await collector.get_snapshot()
        await collector.stop()

        fuel_calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        fuel_snap, _, _ = fuel_calc.update(snap)

        scorer = HealthScorer(n_trees=5, tree_height=4, window_size=50, calibration_samples=10)
        health_snap = scorer.score(snap)

        msg = WebSocketMessage.from_snapshots(snap, health_snap, fuel_snap)
        data = json.loads(msg.model_dump_json())

        # Verify all expected sensor keys are present
        assert "RPM" in data["d"]
        assert "SPEED" in data["d"]
        assert "COOLANT_TEMP" in data["d"]
        assert "ENGINE_LOAD" in data["d"]
        assert "MAF" in data["d"]
        assert "STFT" in data["d"]
        assert "LTFT" in data["d"]
        assert "BATTERY_V" in data["d"]
        assert "OIL_TEMP" in data["d"]
        assert "CATALYST_TEMP" in data["d"]
        assert "FUEL_LEVEL" in data["d"]
        assert "MAP" in data["d"]
        assert "INTAKE_TEMP" in data["d"]
        assert "THROTTLE_POS" in data["d"]

        # Each sensor has v and u
        for key, val in data["d"].items():
            assert "v" in val, f"{key} missing 'v'"
            assert "u" in val, f"{key} missing 'u'"

        # Health scores present
        assert "overall" in data["health"]
        for sub in ["engine", "transmission", "fuel", "cooling", "exhaust", "electrical"]:
            assert sub in data["health"]

        # Fuel data present
        assert "trip_fuel_gal" in data["fuel"]
        assert "tank_pct" in data["fuel"]

    async def test_trip_lifecycle_through_pipeline(self, db, fuel_calc, health_scorer):
        """Full trip: start -> accumulate -> end -> DB has trip record."""
        t = time.time()

        # Simulate driving: 30 ticks at highway speed
        sim = SimulatedCollector(ambient_temp_c=20, initial_fuel_pct=75.0)
        await sim.start()

        active_trip_id = None
        trip_stats_acc = None

        # 80 ticks at 1s intervals:
        # ticks 0-39: driving (speed=100, rpm=2500)
        # ticks 40-49: idle (speed=0, rpm=700) -- simulates pulling over
        # ticks 50-79: engine off (speed=0, rpm=0) -- 30s of rpm=0, well above 10s threshold
        for i in range(80):
            snap = await sim.get_snapshot()
            snap = snap.model_copy(update={
                "speed_kph": 100 if i < 40 else 0,
                "rpm": 2500 if i < 40 else (700 if i < 50 else 0),
                "timestamp": t + i,
            })

            fuel_snap, trip_started, trip_ended = fuel_calc.update(snap)

            if trip_started:
                active_trip_id = await db.start_trip(int(snap.timestamp * 1000))
                trip_stats_acc = TripStatsAccumulator()

            if trip_stats_acc is not None:
                trip_stats_acc.update(snap)

            if trip_ended and active_trip_id is not None:
                summary = fuel_calc.get_completed_trip_summary()
                if summary:
                    stats_json = json.dumps(trip_stats_acc.finalize()) if trip_stats_acc else None
                    await db.end_trip(
                        trip_id=active_trip_id,
                        end_time_ms=int(snap.timestamp * 1000),
                        distance_miles=summary["distance_miles"],
                        fuel_gallons=summary["fuel_gallons"],
                        fuel_cost_usd=summary["fuel_cost_usd"],
                        avg_mpg=summary.get("avg_mpg"),
                        trip_stats=stats_json,
                    )

            health_scorer.score(snap)

        await sim.stop()

        # Verify trip was persisted
        trips = await db.get_recent_trips(limit=5)
        assert len(trips) >= 1, "Expected at least one completed trip in DB"

        trip = trips[0]
        assert trip["end_time"] is not None, "Trip should have an end_time"
        assert trip["distance_miles"] > 0, "Trip should have distance"
        assert trip["fuel_gallons"] > 0, "Trip should have fuel consumption"
        assert trip["trip_stats"] is not None, "Trip should have trip_stats JSON"

        # Parse and verify trip_stats
        stats = json.loads(trip["trip_stats"])
        assert "idle_seconds" in stats
        assert "peak_rpm" in stats
        assert "avg_speed_mph" in stats

    async def test_sensor_readings_batch_persist(self, db):
        """10 snapshots buffered and flushed to DB as a batch."""
        sim = SimulatedCollector(ambient_temp_c=20, initial_fuel_pct=75.0)
        await sim.start()

        snaps = []
        for _ in range(10):
            snap = await sim.get_snapshot()
            snaps.append(snap)

        await sim.stop()

        # Batch write (simulates the 1-second buffer flush)
        await db.insert_readings(snaps)

        counts = await db.get_table_counts()
        assert counts["sensor_readings"] == 10

    async def test_health_scorer_calibration_lifecycle(self):
        """Health scorer starts at -1 (calibrating) and transitions to real scores."""
        scorer = HealthScorer(n_trees=5, tree_height=4, window_size=50, calibration_samples=100)
        sim = SimulatedCollector(ambient_temp_c=20, initial_fuel_pct=75.0)
        await sim.start()

        # During calibration: all scores should be -1
        snap = await sim.get_snapshot()
        health = scorer.score(snap)
        assert health.overall == -1
        assert health.engine == -1

        # Feed enough samples to complete calibration
        for _ in range(110):
            snap = await sim.get_snapshot()
            health = scorer.score(snap)

        await sim.stop()

        # After calibration: scores should be real numbers
        assert health.overall > 0
        assert health.overall <= 100
        assert health.engine > 0

    async def test_websocket_broadcast_format(self):
        """Verify the JSON shape that reaches the frontend matches TypeScript types."""
        sim = SimulatedCollector(ambient_temp_c=20, initial_fuel_pct=75.0)
        await sim.start()
        snap = await sim.get_snapshot()
        await sim.stop()

        fuel_calc = FuelCalculator(tank_capacity_gal=14.8, gas_price_per_gallon=3.50)
        fuel_snap, _, _ = fuel_calc.update(snap)

        scorer = HealthScorer(n_trees=5, tree_height=4, window_size=50, calibration_samples=10)
        health_snap = scorer.score(snap)

        msg = WebSocketMessage.from_snapshots(snap, health_snap, fuel_snap)
        json_str = msg.model_dump_json()
        data = json.loads(json_str)

        # Must match frontend VehicleMessage type
        assert isinstance(data["t"], float)
        assert isinstance(data["d"], dict)
        assert isinstance(data["health"], dict)
        assert isinstance(data["fuel"], dict)

        # FuelData type matching
        fuel = data["fuel"]
        assert "instant_mpg" in fuel
        assert "idle_gph" in fuel
        assert "trip_fuel_gal" in fuel
        assert "trip_cost_usd" in fuel
        assert "trip_distance_mi" in fuel
        assert "tank_pct" in fuel

    async def test_connection_manager_max_limit(self):
        """ConnectionManager rejects connections above MAX_CONNECTIONS."""
        manager = ConnectionManager()

        # Create mock websockets up to MAX_CONNECTIONS (8)
        from backend.ws_manager import MAX_CONNECTIONS
        for i in range(MAX_CONNECTIONS):
            ws = AsyncMock()
            await manager.connect(ws)

        assert manager.client_count == MAX_CONNECTIONS

        # One more should be rejected
        ws_extra = AsyncMock()
        await manager.connect(ws_extra)
        assert manager.client_count == MAX_CONNECTIONS  # unchanged
        ws_extra.close.assert_called_once()

    async def test_fillup_detection_through_pipeline(self, db, fuel_calc):
        """Fuel level jump > 20% triggers fill-up detection and DB write."""
        detector = FillupDetector(
            tank_capacity_gal=14.8,
            gas_price_per_gallon=3.50,
            epa_combined_mpg=31.0,
        )
        t = time.time()

        from backend.obd_manager.models import VehicleSnapshot

        # Feed some readings at 50% fuel level
        for i in range(10):
            snap = VehicleSnapshot(
                timestamp=t + i,
                rpm=700, speed_kph=0, coolant_temp_c=90,
                engine_load_pct=20, throttle_pct=0, intake_air_temp_c=25,
                intake_manifold_kpa=30, maf_gps=2.5, stft_pct=0, ltft_pct=0,
                fuel_level_pct=50.0, catalyst_temp_c=400, oil_temp_c=88,
                battery_voltage=14.2,
            )
            detector.check(snap, miles_since_last_fill=None)

        # Now jump to 95% -- send multiple readings for multi-sample confirmation
        event = None
        for i in range(5):
            snap_full = VehicleSnapshot(
                timestamp=t + 20 + i,
                rpm=700, speed_kph=0, coolant_temp_c=90,
                engine_load_pct=20, throttle_pct=0, intake_air_temp_c=25,
                intake_manifold_kpa=30, maf_gps=2.5, stft_pct=0, ltft_pct=0,
                fuel_level_pct=95.0, catalyst_temp_c=400, oil_temp_c=88,
                battery_voltage=14.2,
            )
            event = detector.check(snap_full, miles_since_last_fill=300.0)
            if event is not None:
                break

        assert event is not None
        assert event.estimated_gallons > 0
        assert event.rune_message  # Rune should have something to say

        # Persist to DB
        await db.insert_fillup(
            detected_at_ms=int(event.detected_at * 1000),
            fuel_level_before=event.fuel_level_before,
            fuel_level_after=event.fuel_level_after,
            estimated_gallons=event.estimated_gallons,
            cost_usd=event.cost_usd,
            mpg_since_last_fill=event.mpg_since_last_fill,
        )

        last_fill = await db.get_last_fillup()
        assert last_fill is not None
        assert last_fill["estimated_gallons"] > 0
