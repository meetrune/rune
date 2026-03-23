"""Rune -- FastAPI application entry point.

Serves the vehicle data API, WebSocket stream, and static frontend build.
The producer loop runs as a background task, collecting OBD data at 10Hz
and broadcasting to all connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.config import settings
from backend.database.db import RuneDatabase
from backend.fuel.calculator import FuelCalculator
from backend.fuel.fillup import FillupDetector
from backend.health.scorer import HealthScorer
from backend.obd_manager.collector import DataCollector, OBDCollector, SimulatedCollector
from backend.obd_manager.models import WebSocketMessage
from backend.ws_manager import ConnectionManager

# Structured JSON logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger("rune")

_start_time: float = 0.0


async def db_maintenance_loop(db: RuneDatabase) -> None:
    """Background task: periodic DB cleanup and WAL checkpoint.

    Runs every hour. Deletes old data, removes junk trips, reclaims space.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # every hour
            result = await db.cleanup(retention_days=90)
            db_size = await db.get_db_size_bytes()
            logger.info(
                "DB maintenance: cleaned %s, size=%.1fMB",
                result, db_size / 1_048_576,
            )
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("DB maintenance error")


async def obd_producer_loop(
    collector: DataCollector,
    fuel_calc: FuelCalculator,
    fillup_detector: FillupDetector,
    health_scorer: HealthScorer,
    db: RuneDatabase,
    manager: ConnectionManager,
) -> None:
    """Background task: collect OBD data at 10Hz, process, broadcast, persist.

    Uses drift-compensated timing to maintain consistent 10Hz rate.
    Buffers sensor readings and flushes to DB every 1 second (10 ticks).
    """
    next_tick = time.monotonic()
    tick_count = 0
    reading_buffer = []
    active_trip_id: int | None = None

    logger.info("Producer loop started at %dHz", settings.ws_rate_hz)

    while True:
        try:
            next_tick += 1.0 / settings.ws_rate_hz

            # Collect snapshot
            snap = await collector.get_snapshot()

            # Fuel calculation
            fuel_snap, trip_started, trip_ended = fuel_calc.update(snap)

            # Trip lifecycle
            if trip_started:
                active_trip_id = await db.start_trip(int(snap.timestamp * 1000))
                if fuel_calc.current_trip is not None:
                    fuel_calc.current_trip.trip_id = active_trip_id

            if trip_ended:
                summary = fuel_calc.get_completed_trip_summary()
                if summary and active_trip_id is not None:
                    avg_mpg = summary.get("avg_mpg")
                    await db.end_trip(
                        trip_id=active_trip_id,
                        end_time_ms=int(snap.timestamp * 1000),
                        distance_miles=summary["distance_miles"],
                        fuel_gallons=summary["fuel_gallons"],
                        fuel_cost_usd=summary["fuel_cost_usd"],
                        avg_mpg=avg_mpg,
                    )
                active_trip_id = None

            # Fill-up detection
            fillup_event = fillup_detector.check(snap)
            if fillup_event:
                await db.insert_fillup(
                    detected_at_ms=int(fillup_event.detected_at * 1000),
                    fuel_level_before=fillup_event.fuel_level_before,
                    fuel_level_after=fillup_event.fuel_level_after,
                    estimated_gallons=fillup_event.estimated_gallons,
                    cost_usd=fillup_event.cost_usd,
                    mpg_since_last_fill=fillup_event.mpg_since_last_fill,
                )
                logger.info("Rune: %s", fillup_event.rune_message)

            # Buffer readings, flush every 10 ticks (1 second)
            reading_buffer.append(snap)
            if len(reading_buffer) >= settings.ws_rate_hz:
                await db.insert_readings(reading_buffer)
                reading_buffer.clear()

            # Health scoring
            health_snap = health_scorer.score(snap)

            # Broadcast to all connected clients
            if manager.client_count > 0:
                msg = WebSocketMessage.from_snapshots(snap, health_snap, fuel_snap)
                await manager.broadcast(msg.model_dump_json())

            tick_count += 1

            # Drift-compensated sleep
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            elif sleep_for < -0.5:
                # More than 500ms behind -- reset to avoid spiral
                next_tick = time.monotonic()
                logger.warning("Producer loop fell behind by %.0fms, resetting", -sleep_for * 1000)

        except asyncio.CancelledError:
            # Flush remaining buffer on shutdown
            if reading_buffer:
                await db.insert_readings(reading_buffer)
            logger.info("Producer loop stopped after %d ticks", tick_count)
            return
        except Exception:
            logger.exception("Error in producer loop")
            await asyncio.sleep(1)  # prevent tight error loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    global _start_time
    _start_time = time.monotonic()

    # Initialize components
    db = RuneDatabase(db_path=settings.db_path)
    await db.initialize()

    collector: DataCollector = (
        SimulatedCollector() if settings.use_simulator else OBDCollector()
    )
    await collector.start()

    fuel_calc = FuelCalculator(
        tank_capacity_gal=settings.fuel_tank_capacity_gal,
        gas_price_per_gallon=settings.gas_price_per_gallon,
    )

    fillup_detector = FillupDetector(
        tank_capacity_gal=settings.fuel_tank_capacity_gal,
        gas_price_per_gallon=settings.gas_price_per_gallon,
        epa_combined_mpg=settings.epa_combined_mpg,
    )

    health_scorer = HealthScorer(
        n_trees=25,
        tree_height=6,
        window_size=500,
        calibration_samples=3000,
    )

    manager = ConnectionManager()

    # Store on app.state for access in route handlers
    app.state.db = db
    app.state.collector = collector
    app.state.fuel_calc = fuel_calc
    app.state.fillup_detector = fillup_detector
    app.state.health_scorer = health_scorer
    app.state.connection_manager = manager

    # Start background tasks
    producer_task = asyncio.create_task(
        obd_producer_loop(collector, fuel_calc, fillup_detector, health_scorer, db, manager)
    )
    maintenance_task = asyncio.create_task(db_maintenance_loop(db))

    logger.info(
        "Rune started: simulator_mode=%s, ws_rate=%dHz, db=%s",
        settings.use_simulator, settings.ws_rate_hz, settings.db_path,
    )

    yield

    # Shutdown -- order matters
    maintenance_task.cancel()
    producer_task.cancel()
    try:
        await producer_task
    except asyncio.CancelledError:
        pass
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass

    await collector.stop()
    await db.close()
    logger.info("Rune shut down")


app = FastAPI(
    title="Rune",
    version="0.1.0",
    description="The translation layer between Rune and the human who drives him",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.4.1:8080", "http://localhost:8080", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/debug")
async def serve_debug() -> FileResponse:
    """Serve the debug dashboard HTML."""
    debug_path = Path(__file__).parent.parent / "debug.html"
    return FileResponse(debug_path, media_type="text/html")


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """Server health check."""
    return JSONResponse({
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "obd_connected": False,
        "simulator_mode": settings.use_simulator,
        "ws_clients": app.state.connection_manager.client_count,
        "version": "0.1.0",
    })


@app.get("/api/debug")
async def debug_info() -> JSONResponse:
    """Full system state for the debug dashboard."""
    db: RuneDatabase = app.state.db
    fuel_calc: FuelCalculator = app.state.fuel_calc
    fillup_det: FillupDetector = app.state.fillup_detector
    collector = app.state.collector
    manager: ConnectionManager = app.state.connection_manager

    # Safety gate
    from backend.obd_manager.connection import ALLOWED_MODES, BLOCKED_MODES

    # DB row counts
    table_counts = await db.get_table_counts()

    # Recent trips
    recent_trips = await db.get_recent_trips(limit=5)

    # Last fillup
    last_fillup = await db.get_last_fillup()

    # Simulator state
    sim = collector._sim if hasattr(collector, '_sim') else None
    sim_info = {}
    if sim:
        sim_info = {
            "phase": sim.phase.value,
            "elapsed_seconds": round(sim._state.elapsed, 1),
            "ambient_temp_c": sim._state.ambient_temp_c,
            "scenario_index": sim._state.scenario_index,
            "scenario_total": len(sim._scenario),
            "anomalies_configured": len(sim._anomalies),
        }

    # Fuel calculator state
    trip_info = None
    if fuel_calc.current_trip:
        t = fuel_calc.current_trip
        trip_info = {
            "trip_id": t.trip_id,
            "start_time": t.start_time,
            "distance_miles": round(t.distance_miles, 4),
            "fuel_gallons": round(t.fuel_gallons, 6),
            "fuel_cost_usd": round(t.fuel_gallons * settings.gas_price_per_gallon, 2),
            "idle_since": t.idle_since,
        }

    db_size = await db.get_db_size_bytes()

    return JSONResponse({
        "safety_gate": {
            "allowed_modes": sorted(ALLOWED_MODES),
            "blocked_modes": sorted(BLOCKED_MODES),
            "mode": "whitelist",
        },
        "database": {
            "path": settings.db_path,
            "journal_mode": "wal",
            "size_mb": round(db_size / 1_048_576, 2),
            "retention_days": 90,
            "tables": table_counts,
        },
        "recent_trips": recent_trips,
        "last_fillup": last_fillup,
        "simulator": sim_info,
        "fuel_calculator": {
            "trip_active": fuel_calc.is_trip_active,
            "current_trip": trip_info,
            "gas_price_per_gallon": settings.gas_price_per_gallon,
            "tank_capacity_gal": settings.fuel_tank_capacity_gal,
        },
        "health_scorer": app.state.health_scorer.get_debug_state(),
        "websocket": {
            "clients_connected": manager.client_count,
            "rate_hz": settings.ws_rate_hz,
        },
        "server": {
            "uptime_seconds": round(time.monotonic() - _start_time, 2),
            "simulator_mode": settings.use_simulator,
            "version": "0.1.0",
        },
    })


@app.websocket("/ws/vehicle-data")
async def vehicle_data_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming vehicle data to the frontend.

    The producer loop broadcasts to all connected clients. This handler
    just registers/unregisters the client and waits for disconnect.
    Must run iter_text() to detect disconnects (pure-push won't see them).
    """
    manager: ConnectionManager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    try:
        async for _ in websocket.iter_text():
            pass  # blocks until client disconnects
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
