"""Rune -- FastAPI application entry point.

Serves the vehicle data API, WebSocket stream, and static frontend build.
The producer loop runs as a background task, collecting OBD data at 10Hz
and broadcasting to all connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from pathlib import Path

from fastapi import FastAPI, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.api.logs import log_buffer
from backend.config import settings
from backend.database.db import RuneDatabase
from backend.fuel.calculator import FuelCalculator
from backend.fuel.fillup import FillupDetector
from backend.fuel.trip_stats import TripStatsAccumulator
from backend.health.scorer import HealthScorer
from backend.obd_manager.can_listener import CANListener
from backend.obd_manager.collector import DataCollector, OBDCollector, SimulatedCollector
from backend.obd_manager.models import FuelSnapshot, HealthSnapshot, VehicleSnapshot, WebSocketMessage
from backend.sensors.thermal import ThermalManager
from backend.sensors.wittypi import SimulatedWittyPiReader, WittyPiReader
from backend.ws_manager import ConnectionManager

# Resilient export
from backend.api.export import (
    cleanup_stale_sessions,
    complete_export as complete_export_session,
    get_export_session,
    prepare_export,
    stream_export,
)
from fastapi.responses import StreamingResponse

# Intelligence Layer
from backend.intelligence.alert_queue import AlertQueue
from backend.intelligence import sync_engine
from backend.intelligence.battery_monitor import BatteryMonitor
from backend.intelligence.cold_start import ColdStartProfiler
from backend.intelligence.trip_scorer import TripScorer
from backend.intelligence.thermal_guardian import ThermalGuardian
from backend.intelligence.maintenance import MaintenanceTracker
from backend.intelligence.can_decoder import CANDecoder
from backend.intelligence.wittypi_scheduler import (
    clear_schedule,
    emergency_shutdown,
    write_parked_schedule,
)

# Structured JSON logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger("rune")

# Install ring buffer handler for /api/logs endpoint
log_buffer.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(log_buffer)

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
            # Clean up stale export sessions (chunks on disk + DB keys)
            stale = await cleanup_stale_sessions(db)
            if stale:
                logger.info("Export cleanup: removed %d stale sessions", stale)
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
    pi_reader: WittyPiReader | SimulatedWittyPiReader,
    thermal_mgr: ThermalManager,
) -> None:
    """Background task: collect OBD data at 10Hz, process, broadcast, persist.

    Uses drift-compensated timing to maintain consistent 10Hz rate.
    Buffers sensor readings and flushes to DB every 1 second (10 ticks).
    Pi sensors (Witty Pi I2C) are read once per second (tick_count % ws_rate == 0).
    Thermal manager evaluates once per second and can reduce WebSocket rate.
    """
    next_tick = time.monotonic()
    tick_count = 0
    reading_buffer: list[VehicleSnapshot] = []
    active_trip_id: int | None = None
    trip_stats_acc: TripStatsAccumulator | None = None
    effective_ws_hz = settings.ws_rate_hz  # can be reduced by thermal manager
    # Carry forward last Pi sensor values between 1Hz reads
    last_vin: float | None = None
    last_armrest: float | None = None
    last_cpu_temp: float | None = None
    last_current: float | None = None

    logger.info("Producer loop started at %dHz", settings.ws_rate_hz)

    while True:
        try:
            # Check if go-live was signaled (swap simulator for real OBD)
            if hasattr(app, 'state') and hasattr(app.state, 'go_live_event'):
                if app.state.go_live_event.is_set():
                    app.state.go_live_event.clear()
                    logger.warning("Go-live signal received. Swapping to OBDCollector...")
                    await collector.stop()
                    new_collector = OBDCollector()
                    try:
                        await new_collector.start()
                    except Exception:
                        logger.critical("OBDCollector failed to start during go-live", exc_info=True)
                        # Don't update collector -- let outer except handle retry
                        raise
                    collector = new_collector
                    app.state.collector = collector
                    settings.use_simulator = False
                    next_tick = time.monotonic()  # reset drift clock after slow startup
                    logger.warning("Go-live complete. Now using real OBD connection.")

            next_tick += 1.0 / max(effective_ws_hz, 1)

            # Collect OBD snapshot
            snap = await collector.get_snapshot()

            # Read Pi-side sensors once per second (not 10Hz -- I2C is slow)
            # Wrapped in to_thread to avoid blocking the async loop with
            # time.sleep() retries in the I2C read methods.
            if tick_count % settings.ws_rate_hz == 0:
                pi_snap = await asyncio.to_thread(pi_reader.read_snapshot)
                last_vin = pi_snap.vin_voltage
                last_armrest = pi_snap.armrest_temp_c
                last_cpu_temp = pi_snap.cpu_temp_c
                last_current = pi_snap.iout_amps

                # Thermal management -- evaluate once per second
                thermal_state = thermal_mgr.update(
                    cpu_temp_c=pi_snap.cpu_temp_c,
                    armrest_temp_c=pi_snap.armrest_temp_c,
                    vin_voltage=pi_snap.vin_voltage,
                )

                # Adjust WebSocket rate based on thermal status
                if thermal_state.recommended_ws_hz != effective_ws_hz:
                    effective_ws_hz = thermal_state.recommended_ws_hz
                    logger.info(
                        "Thermal %s: WebSocket rate adjusted to %dHz",
                        thermal_state.overall_status.value, effective_ws_hz,
                    )

                # Log thermal warnings
                if thermal_state.message:
                    logger.warning("Thermal: %s", thermal_state.message)

                # Intelligence: battery monitor (once per second with Vin reading)
                if settings.intelligence_enabled and pi_snap.vin_voltage is not None:
                    try:
                        engine_running = snap.rpm > 400
                        await app.state.battery_monitor.update(
                            vin_voltage=pi_snap.vin_voltage,
                            engine_running=engine_running,
                        )
                    except Exception:
                        logger.debug("Battery monitor update failed", exc_info=True)

                # Intelligence: parked thermal guardian (once per minute when no active trip)
                if settings.intelligence_enabled and active_trip_id is None and tick_count % (settings.ws_rate_hz * 60) == 0:
                    try:
                        guardian: ThermalGuardian = app.state.thermal_guardian
                        parked_result = await guardian.check_parked_state(
                            armrest_temp_c=pi_snap.armrest_temp_c,
                            cpu_temp_c=pi_snap.cpu_temp_c,
                            vin_voltage=pi_snap.vin_voltage,
                            alert_queue=app.state.alert_queue,
                        )
                        # Emergency shutdown: too hot, shut down immediately
                        if guardian.should_shutdown:
                            if reading_buffer:
                                await db.insert_readings(reading_buffer)
                                reading_buffer.clear()
                            write_parked_schedule(
                                wake_seconds=30,
                                sleep_hours=settings.thermal_extreme_wake_hours,
                            )
                            temp_val = parked_result.armrest_temp_c if parked_result.armrest_temp_c is not None else parked_result.cpu_temp_c
                            emergency_shutdown(f"Enclosure at {temp_val}C")
                            return
                    except Exception:
                        logger.warning("Parked thermal check failed", exc_info=True)

                # Thermal shutdown
                if thermal_state.should_shutdown:
                    logger.critical(
                        "THERMAL SHUTDOWN: CPU=%.1fC armrest=%.1fC -- initiating graceful shutdown",
                        thermal_state.cpu_temp_filtered, thermal_state.armrest_temp_filtered,
                    )
                    # Flush buffer before shutdown
                    if reading_buffer:
                        await db.insert_readings(reading_buffer)
                        reading_buffer.clear()
                    # Import here to avoid circular -- shutdown is a rare path
                    import subprocess
                    try:
                        result = subprocess.run(
                            ["sudo", "shutdown", "-h", "+1",
                             "Rune thermal shutdown: armrest too hot"],
                            capture_output=True, text=True, timeout=5,
                        )
                        if result.returncode != 0:
                            logger.critical(
                                "Thermal shutdown command failed (rc=%d): %s",
                                result.returncode, result.stderr,
                            )
                    except Exception:
                        logger.critical("Failed to execute thermal shutdown", exc_info=True)
                    return

            # Carry forward Pi sensor values so every WS message includes them
            snap.vin_voltage = last_vin
            snap.armrest_temp_c = last_armrest
            snap.pi_cpu_temp_c = last_cpu_temp
            snap.pi_current_a = last_current

            # Fuel calculation
            try:
                fuel_snap, trip_started, trip_ended = fuel_calc.update(snap)
            except Exception:
                logger.warning("Fuel calculation failed, using defaults", exc_info=True)
                fuel_snap = FuelSnapshot(tank_pct=snap.fuel_level_pct)
                trip_started = False
                trip_ended = False

            # Trip lifecycle
            if trip_started:
                try:
                    active_trip_id = await db.start_trip(int(snap.timestamp * 1000))
                except Exception:
                    logger.warning("Failed to start trip in DB", exc_info=True)
                    active_trip_id = None
                trip_stats_acc = TripStatsAccumulator()
                if fuel_calc.current_trip is not None:
                    fuel_calc.current_trip.trip_id = active_trip_id

                # Intelligence: trip start hooks
                if settings.intelligence_enabled:
                    try:
                        app.state.trip_scorer.start_trip()
                        app.state.cold_start_profiler.on_trip_start(
                            coolant_c=snap.coolant_temp_c,
                            ambient_c=snap.intake_air_temp_c,
                        )
                        # Clear Witty Pi schedule -- car is running, stay on continuously
                        clear_schedule()
                    except Exception:
                        logger.warning("Intelligence trip-start hook failed", exc_info=True)

            # Accumulate trip stats every tick
            if trip_stats_acc is not None:
                trip_stats_acc.update(snap)

            # Intelligence: per-tick updates (trip scorer, cold start)
            if settings.intelligence_enabled and active_trip_id is not None:
                try:
                    dt = 1.0 / max(effective_ws_hz, 1)
                    app.state.trip_scorer.update(
                        throttle_pct=snap.throttle_pct,
                        speed_kph=snap.speed_kph,
                        rpm=snap.rpm,
                        dt_seconds=dt,
                    )
                    app.state.cold_start_profiler.on_reading(snap.coolant_temp_c)
                except Exception:
                    logger.warning("Intelligence per-tick update failed", exc_info=True)

            if trip_ended:
                try:
                    summary = fuel_calc.get_completed_trip_summary()
                    if summary and active_trip_id is not None:
                        import json
                        avg_mpg = summary.get("avg_mpg")
                        stats_json = json.dumps(trip_stats_acc.finalize()) if trip_stats_acc else None
                        await db.end_trip(
                            trip_id=active_trip_id,
                            end_time_ms=int(snap.timestamp * 1000),
                            distance_miles=summary["distance_miles"],
                            fuel_gallons=summary["fuel_gallons"],
                            fuel_cost_usd=summary["fuel_cost_usd"],
                            avg_mpg=avg_mpg,
                            trip_stats=stats_json,
                        )
                        # Broadcast trip_ended event to frontend
                        if manager.client_count > 0:
                            duration_min = 0.0
                            if summary.get("start_time"):
                                duration_min = (snap.timestamp - summary["start_time"]) / 60
                            trip_event = json.dumps({
                                "type": "trip_ended",
                                "trip": {
                                    "trip_id": active_trip_id,
                                    "distance_miles": round(summary["distance_miles"], 1),
                                    "fuel_gallons": round(summary["fuel_gallons"], 3),
                                    "fuel_cost_usd": round(summary["fuel_cost_usd"], 2),
                                    "avg_mpg": round(avg_mpg, 1) if avg_mpg else None,
                                    "duration_minutes": round(duration_min, 1),
                                    "stats": trip_stats_acc.finalize() if trip_stats_acc else None,
                                },
                            })
                            await manager.broadcast(trip_event)
                        # Intelligence: trip-end hooks (scoring, cold start, maintenance)
                        if settings.intelligence_enabled:
                            try:
                                # Trip scoring
                                trip_distance = summary["distance_miles"]
                                if avg_mpg and trip_distance > 0.5:
                                    trip_score = app.state.trip_scorer.score_trip(
                                        trip_mpg=avg_mpg,
                                        trip_distance_miles=trip_distance,
                                    )
                                    logger.info(
                                        "Trip score: composite=%d efficiency=%d smoothness=%d idle=%d",
                                        int(trip_score.composite), int(trip_score.efficiency),
                                        int(trip_score.smoothness), int(trip_score.idle_ratio),
                                    )

                                # Cold-start record
                                await app.state.cold_start_profiler.on_trip_end(
                                    trip_id=active_trip_id, db=db,
                                )

                                # Write Witty Pi parked schedule -- car is off now
                                write_parked_schedule(
                                    wake_seconds=30,
                                    sleep_hours=settings.thermal_normal_wake_hours,
                                )

                                # Maintenance check
                                cumulative_miles = await db.get_cumulative_miles()
                                await app.state.maintenance_tracker.check_maintenance(
                                    current_odometer_miles=cumulative_miles,
                                    db=db,
                                    alert_queue=app.state.alert_queue,
                                    avg_oil_temp_c=snap.oil_temp_c if snap.oil_temp_c > 0 else None,
                                )
                            except Exception:
                                logger.warning("Intelligence trip-end hooks failed", exc_info=True)

                except Exception:
                    logger.warning("Failed to end trip in DB", exc_info=True)
                active_trip_id = None
                trip_stats_acc = None

            # Fill-up detection -- check once per second (not 10x/sec)
            # DB queries for miles_since_fill are expensive on SD card
            try:
                fillup_event = None
                if tick_count % settings.ws_rate_hz == 0:
                    miles_since_fill: float | None = None
                    last_fill = await db.get_last_fillup()
                    if last_fill:
                        recent = await db.get_recent_trips(limit=100)
                        miles_since_fill = sum(
                            t["distance_miles"] for t in recent
                            if t["start_time"] >= last_fill["detected_at"]
                        )
                    fillup_event = fillup_detector.check(snap, miles_since_last_fill=miles_since_fill)
                else:
                    fillup_event = fillup_detector.check(snap, miles_since_last_fill=None)
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
            except Exception:
                logger.warning("Fillup detection failed, skipping this tick", exc_info=True)

            # Buffer readings, flush every 10 ticks (1 second)
            reading_buffer.append(snap)
            if len(reading_buffer) >= settings.ws_rate_hz:
                try:
                    await db.insert_readings(reading_buffer)
                except Exception:
                    logger.exception("DB write failed, dropping %d readings", len(reading_buffer))
                reading_buffer.clear()
            elif len(reading_buffer) > 100:
                # Safety cap: if buffer grows beyond 100 (DB writes failing), drop old data
                logger.warning("Reading buffer overflow (%d), clearing", len(reading_buffer))
                reading_buffer.clear()

            # Health scoring
            try:
                health_snap = health_scorer.score(snap)
            except Exception:
                logger.warning("Health scoring failed, using sentinel values", exc_info=True)
                health_snap = HealthSnapshot(
                    overall=-1, engine=-1, transmission=-1,
                    fuel=-1, cooling=-1, exhaust=-1, electrical=-1,
                )

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

    # Pi-side sensors (Witty Pi 4 I2C + CPU thermal zone)
    pi_reader: WittyPiReader | SimulatedWittyPiReader = (
        SimulatedWittyPiReader() if settings.use_simulator else WittyPiReader()
    )
    await pi_reader.start()

    thermal_mgr = ThermalManager()

    # Raw CAN listener (passive, read-only, port 35000)
    can_listener: CANListener | None = None
    if settings.can_logging_enabled and not settings.use_simulator:
        can_listener = CANListener(
            host=settings.wican_host,
            port=settings.wican_can_port,
        )
        await can_listener.start(db=db)

    # Store on app.state for access in route handlers
    app.state.db = db
    app.state.collector = collector
    app.state.fuel_calc = fuel_calc
    app.state.fillup_detector = fillup_detector
    app.state.health_scorer = health_scorer
    app.state.connection_manager = manager
    app.state.pi_reader = pi_reader
    app.state.thermal_mgr = thermal_mgr
    app.state.go_live_event = asyncio.Event()
    app.state.can_listener = can_listener

    # Intelligence Layer
    if settings.intelligence_enabled:
        alert_queue = AlertQueue(db, rate_limit_seconds=settings.alert_rate_limit_seconds)
        battery_monitor = BatteryMonitor(alert_queue=alert_queue)
        cold_start_profiler = ColdStartProfiler(alert_queue=alert_queue)
        await cold_start_profiler.load_history(db)
        trip_scorer = TripScorer()
        thermal_guardian = ThermalGuardian()
        maintenance_tracker = MaintenanceTracker()
        can_decoder = CANDecoder()
        app.state.alert_queue = alert_queue
        app.state.battery_monitor = battery_monitor
        app.state.cold_start_profiler = cold_start_profiler
        app.state.trip_scorer = trip_scorer
        app.state.thermal_guardian = thermal_guardian
        app.state.maintenance_tracker = maintenance_tracker
        app.state.can_decoder = can_decoder
    else:
        app.state.alert_queue = None
        app.state.battery_monitor = None
        app.state.cold_start_profiler = None
        app.state.trip_scorer = None
        app.state.thermal_guardian = None
        app.state.maintenance_tracker = None
        app.state.can_decoder = None

    # Start background tasks
    producer_task = asyncio.create_task(
        obd_producer_loop(
            collector, fuel_calc, fillup_detector, health_scorer,
            db, manager, pi_reader, thermal_mgr,
        )
    )
    app.state.producer_task = producer_task
    maintenance_task = asyncio.create_task(db_maintenance_loop(db))

    logger.info(
        "Rune started: simulator_mode=%s, ws_rate=%dHz, db=%s, can_logging=%s",
        settings.use_simulator, settings.ws_rate_hz, settings.db_path,
        can_listener is not None,
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

    if can_listener is not None:
        await can_listener.stop()
    await collector.stop()
    await pi_reader.stop()
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


# Path resolution: works in both dev (pi/backend/) and Pi deployment (/opt/rune/backend/)
_app_root = Path(__file__).parent.parent  # pi/ in dev, /opt/rune/ on Pi

# Serve static frontend files (models, assets)
# Dev: repo-root/pixel/frontend/public, Pi: /opt/rune/frontend/public
_frontend_dir = _app_root / "frontend" / "public"
if not _frontend_dir.exists():
    _frontend_dir = _app_root.parent / "pixel" / "frontend" / "public"
if _frontend_dir.exists():
    app.mount("/frontend/public", StaticFiles(directory=str(_frontend_dir)), name="frontend-static")



@app.get("/api/health")
async def health_check() -> JSONResponse:
    """Server health check."""
    return JSONResponse({
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "obd_connected": app.state.collector.is_running if hasattr(app.state.collector, 'is_running') else settings.use_simulator,
        "simulator_mode": settings.use_simulator,
        "ws_clients": app.state.connection_manager.client_count,
        "version": "0.1.0",
    })


@app.get("/api/trips")
async def get_trips(limit: int = Query(default=20, ge=1, le=100)) -> JSONResponse:
    """Trip history for the Summary screen."""
    import json as _json
    db: RuneDatabase = app.state.db
    trips = await db.get_recent_trips(limit=limit)
    # Parse trip_stats JSON blobs
    for t in trips:
        if t.get("trip_stats") and isinstance(t["trip_stats"], str):
            try:
                t["trip_stats"] = _json.loads(t["trip_stats"])
            except (ValueError, TypeError):
                t["trip_stats"] = None
    return JSONResponse({"trips": trips})


@app.get("/api/debug")
async def debug_info() -> JSONResponse:
    """Full system state for the debug dashboard."""
    db: RuneDatabase = app.state.db
    fuel_calc: FuelCalculator = app.state.fuel_calc
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
            "engine_off_since": t.engine_off_since,
            "speed_idle_since": t.speed_idle_since,
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
        "thermal": app.state.thermal_mgr.get_debug_state(),
        "pi_sensors": {
            "witty_pi_available": app.state.pi_reader.is_available,
        },
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


@app.get("/api/diagnostics")
async def diagnostics() -> JSONResponse:
    """Run comprehensive system diagnostics."""
    from backend.diagnostics import run_all_checks
    results = await run_all_checks(app.state)
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    warned = sum(1 for r in results if r.status == "warn")
    return JSONResponse({
        "summary": {"total": len(results), "pass": passed, "fail": failed, "warn": warned},
        "checks": [r.to_dict() for r in results],
        "timestamp": time.time(),
    })


@app.get("/diagnostics")
async def serve_diagnostics() -> FileResponse:
    """Serve the diagnostic dashboard."""
    diag_path = _app_root / "diagnostics" / "diagnostics.html"
    return FileResponse(diag_path, media_type="text/html")


@app.get("/diagnostics.js")
async def serve_diagnostics_js() -> FileResponse:
    """Serve the diagnostics dashboard JavaScript."""
    js_path = _app_root / "diagnostics" / "diagnostics.js"
    return FileResponse(js_path, media_type="application/javascript")


@app.get("/diagnostics-topology.js")
async def serve_diagnostics_topology_js() -> FileResponse:
    """Serve the interactive topology JavaScript."""
    js_path = _app_root / "diagnostics" / "diagnostics-topology.js"
    return FileResponse(js_path, media_type="application/javascript")


# --- Advanced Diagnostics Endpoints ---


@app.get("/api/health-trend")
async def health_trend(hours: int = Query(default=1, ge=1, le=168)) -> JSONResponse:
    """Health score trend for sparkline visualization."""
    db: RuneDatabase = app.state.db
    scores = await db.get_health_trend(hours=hours)
    return JSONResponse({"scores": scores, "hours": hours})


@app.get("/api/system")
async def system_info() -> JSONResponse:
    """System metrics: CPU, RAM, disk, temp, uptime."""
    from backend.api.system import get_system_info
    info = await get_system_info()
    return JSONResponse(info)


@app.post("/api/obd/test")
async def obd_test() -> JSONResponse:
    """Test OBD connection by generating a snapshot and checking collector state.

    In simulator mode: returns simulated ELM327 version.
    In live mode: verifies the collector can produce a snapshot (proves TCP
    connectivity to WiCAN Pro and successful PID polling). Does NOT send
    raw AT commands -- ATI/ATRV are ELM327 chip commands that bypass the
    OBD mode whitelist and belong to the connection init sequence, not
    a diagnostic endpoint.
    """
    t = time.monotonic()
    collector = app.state.collector
    is_sim = isinstance(collector, SimulatedCollector)

    if is_sim:
        elapsed = (time.monotonic() - t) * 1000
        return JSONResponse({
            "success": True,
            "response": "ELM327 v2.3 (simulated)",
            "mode": "simulator",
            "duration_ms": round(elapsed, 2),
        })

    # Live mode: verify OBD connection by requesting a snapshot
    # This proves TCP connectivity + ELM327 init + PID polling works
    try:
        snap = await collector.get_snapshot()
        elapsed = (time.monotonic() - t) * 1000
        return JSONResponse({
            "success": True,
            "response": f"OBD connected. RPM={snap.rpm:.0f}, coolant={snap.coolant_temp_c:.1f}C",
            "mode": "live",
            "duration_ms": round(elapsed, 2),
        })
    except Exception as e:
        elapsed = (time.monotonic() - t) * 1000
        return JSONResponse({
            "success": False,
            "error": str(e),
            "mode": "live",
            "duration_ms": round(elapsed, 2),
        }, status_code=500)


@app.post("/api/test/integration")
async def integration_test() -> JSONResponse:
    """Deep integration test: snapshot -> DB -> health -> fuel -> WS check."""
    from backend.diagnostics import run_integration_test
    result = await run_integration_test(app.state)
    status_code = 200 if result["overall"] == "pass" else 500
    return JSONResponse(result, status_code=status_code)


@app.get("/api/logs")
async def get_logs(
    lines: int = Query(default=50, ge=1, le=500),
    level: str = Query(default="DEBUG", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
) -> JSONResponse:
    """Recent log entries from the in-memory ring buffer.

    Filterable by minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    Returns newest first.
    """
    records = log_buffer.get_records(min_level=level, limit=lines)
    return JSONResponse({
        "logs": records,
        "total_buffered": log_buffer.count,
        "filter_level": level.upper(),
    })


@app.get("/api/config")
async def get_config() -> JSONResponse:
    """All RuneSettings values. Read-only, for diagnostics display."""
    config_dict = settings.model_dump()
    # Group settings by category for frontend display
    return JSONResponse({
        "settings": config_dict,
        "categories": {
            "server": ["server_host", "server_port", "log_level"],
            "obd": [
                "obd_fast",
                "wican_host", "wican_port", "obd_cmd_timeout",
                "obd_reconnect_max_backoff", "obd_circuit_breaker_threshold",
                "obd_circuit_breaker_cooldown", "obd_stale_threshold",
                "obd_mode22_enabled",
            ],
            "vehicle": [
                "fuel_tank_capacity_gal", "epa_combined_mpg",
                "gas_price_per_gallon",
            ],
            "websocket": ["ws_rate_hz"],
            "database": ["db_path"],
            "modes": ["use_simulator"],
        },
    })


@app.post("/api/control/checkpoint")
async def control_checkpoint() -> JSONResponse:
    """Force a WAL checkpoint. Transfers pending writes to main DB file."""
    from backend.api.controls import force_checkpoint
    result = await force_checkpoint(app.state.db)
    status_code = 200 if result["success"] else 500
    return JSONResponse(result, status_code=status_code)


@app.post("/api/control/recalibrate")
async def control_recalibrate() -> JSONResponse:
    """Reset health scorer calibration. Scores will show -1 for ~5 minutes."""
    from backend.api.controls import recalibrate_health_scorer
    result = await recalibrate_health_scorer(app.state.health_scorer)
    status_code = 200 if result["success"] else 500
    return JSONResponse(result, status_code=status_code)


@app.post("/api/control/restart-producer")
async def control_restart_producer() -> JSONResponse:
    """Restart the OBD producer loop. Stops and re-creates the background task."""
    t = time.monotonic()
    try:
        old_task: asyncio.Task[None] = app.state.producer_task
        old_task.cancel()
        try:
            await old_task
        except (asyncio.CancelledError, Exception):
            pass  # old task is gone regardless of how it ended

        # Re-create the producer task with the same components
        new_task = asyncio.create_task(
            obd_producer_loop(
                app.state.collector,
                app.state.fuel_calc,
                app.state.fillup_detector,
                app.state.health_scorer,
                app.state.db,
                app.state.connection_manager,
                app.state.pi_reader,
                app.state.thermal_mgr,
            )
        )
        app.state.producer_task = new_task
        elapsed = (time.monotonic() - t) * 1000

        logger.info("Producer loop restarted via manual control in %.1fms", elapsed)
        return JSONResponse({
            "success": True,
            "duration_ms": round(elapsed, 2),
            "message": "Producer loop restarted. Data collection resumed.",
        })
    except Exception as e:
        elapsed = (time.monotonic() - t) * 1000
        logger.error("Producer restart failed: %s", e)
        return JSONResponse({
            "success": False,
            "error": str(e),
            "duration_ms": round(elapsed, 2),
        }, status_code=500)


@app.post("/api/control/go-live")
async def control_go_live() -> JSONResponse:
    """Remove all simulation data and switch to real OBD. One-way operation."""
    from backend.api.controls import go_live
    result = await go_live(
        db=app.state.db,
        scorer=app.state.health_scorer,
        go_live_event=app.state.go_live_event,
        use_simulator=settings.use_simulator,
    )
    status_code = 200 if result["success"] else 500
    return JSONResponse(result, status_code=status_code)


@app.post("/api/control/reset-data")
async def control_reset_data() -> JSONResponse:
    """Wipe all stored data and reset calibration. Works in any mode.

    Use after hardware testing to start fresh before daily driving.
    Does not change collector mode (sim/live stays as-is).
    """
    from backend.api.controls import reset_all_data
    result = await reset_all_data(
        db=app.state.db,
        scorer=app.state.health_scorer,
    )
    status_code = 200 if result["success"] else 500
    return JSONResponse(result, status_code=status_code)


@app.get("/api/export")
async def export_database() -> FileResponse:
    """Export the full SQLite database for offline analysis.

    Creates a safe backup (does not lock the live DB) and returns it
    as a downloadable file. Used by the iOS Shortcut to pull raw data
    for the Mac training pipeline.
    """
    import tempfile
    db: RuneDatabase = app.state.db
    backup_path = os.path.join(tempfile.gettempdir(), "rune-export.db")
    await db.backup(backup_path)
    return FileResponse(
        backup_path,
        filename="rune.db",
        media_type="application/x-sqlite3",
    )


# --- Resilient Export API (chunked, SHA-verified, resumable) ---
# Replaces /api/export for large DBs. Pi splits backup into 5MB chunks,
# verifies each chunk's SHA-256, then streams the reassembled file.
# If WiFi drops, iPhone re-hits the same session URL -- same bytes, same SHA.

# Concurrency lock: only one export prep at a time
_export_lock = asyncio.Lock()


@app.post("/api/export/prepare")
async def export_prepare_endpoint(
    chunk_size_mb: int = Query(default=5, ge=1, le=50),
) -> JSONResponse:
    """Create a backup, split into chunks, compute SHAs. Returns session manifest."""
    if _export_lock.locked():
        return JSONResponse(
            {"error": "export already in progress"},
            status_code=409,
        )
    async with _export_lock:
        db: RuneDatabase = app.state.db
        try:
            session = await prepare_export(db, chunk_size_bytes=chunk_size_mb * 1024 * 1024)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=507)
    return JSONResponse(session.model_dump(exclude={"export_dir"}))


@app.get("/api/export/status/{session_id}")
async def export_status_endpoint(session_id: str) -> JSONResponse:
    """Check if an export session is still valid."""
    db: RuneDatabase = app.state.db
    session = await get_export_session(db, session_id)
    if session is None:
        return JSONResponse({"valid": False}, status_code=404)
    return JSONResponse({
        "valid": True,
        "session_id": session.session_id,
        "total_bytes": session.total_bytes,
        "total_sha256": session.total_sha256,
        "chunk_count": session.chunk_count,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
    })


@app.get("/api/export/stream/{session_id}")
async def export_stream_endpoint(session_id: str) -> StreamingResponse:
    """Stream the verified backup file. Idempotent -- same session = same bytes."""
    db: RuneDatabase = app.state.db
    session = await get_export_session(db, session_id)
    if session is None:
        return JSONResponse(
            {"error": "session not found or expired, call /api/export/prepare"},
            status_code=404,
        )
    return StreamingResponse(
        stream_export(session),
        media_type="application/x-sqlite3",
        headers={
            "Content-Length": str(session.total_bytes),
            "Content-Disposition": 'attachment; filename="rune.db"',
            "X-Export-SHA256": session.total_sha256,
            "X-Session-ID": session.session_id,
        },
    )


@app.post("/api/export/complete/{session_id}")
async def export_complete_endpoint(session_id: str) -> JSONResponse:
    """Clean up temp files after successful download."""
    db: RuneDatabase = app.state.db
    result = await complete_export_session(db, session_id)
    status = 200 if result.get("ok") else 404
    return JSONResponse(result, status_code=status)


# --- Intelligence Layer: Sync API ---


class SyncAckRequest(BaseModel):
    """Request body for POST /api/sync/ack."""
    alert_ids: list[int] = Field(default_factory=list)
    cursor: str | None = None  # ISO 8601 -- when the iPhone relayed to ntfy


@app.get("/api/sync/alerts")
async def sync_get_alerts() -> JSONResponse:
    """Return all unsynced alerts for iPhone relay to ntfy.sh."""
    if not settings.intelligence_enabled:
        return JSONResponse({"alerts": [], "count": 0, "fetched_at": ""})
    db: RuneDatabase = app.state.db
    result = await sync_engine.get_unsynced_alerts(db)
    return JSONResponse(result)


@app.get("/api/sync/delta")
async def sync_get_delta(
    since: str = Query(..., description="ISO 8601 timestamp -- fetch data after this point"),
) -> Response:
    """Return trip summaries + sensor reading count since a timestamp.

    Includes X-Rune-Checksum header (SHA-256 of JSON body) for integrity verification.
    """
    if not settings.intelligence_enabled:
        return JSONResponse({"error": "intelligence layer disabled"}, status_code=503)
    db: RuneDatabase = app.state.db
    try:
        data = await sync_engine.get_delta(db, since_iso=since)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    body = json.dumps(data).encode()
    checksum = hashlib.sha256(body).hexdigest()
    return Response(
        content=body,
        media_type="application/json",
        headers={"X-Rune-Checksum": checksum},
    )


@app.post("/api/sync/ack")
async def sync_ack(req: SyncAckRequest) -> JSONResponse:
    """Mark alerts as synced and advance the sync cursor. Idempotent."""
    if not settings.intelligence_enabled:
        return JSONResponse({"error": "intelligence layer disabled"}, status_code=503)
    db: RuneDatabase = app.state.db
    result = await sync_engine.ack_sync(db, alert_ids=req.alert_ids, cursor_iso=req.cursor)
    return JSONResponse(result)


@app.get("/api/sync/status")
async def sync_status() -> JSONResponse:
    """Pending alerts count, readings since last sync, last sync time."""
    if not settings.intelligence_enabled:
        return JSONResponse({"pending_alerts": 0, "last_sync_at": None, "readings_since_sync": 0, "server_time": "", "has_data": False})
    db: RuneDatabase = app.state.db
    result = await sync_engine.get_sync_status(db)
    return JSONResponse(result)


# --- Intelligence Layer: Maintenance API ---


class MaintenanceDoneRequest(BaseModel):
    """Request body for POST /api/maintenance/done."""
    item: str  # MaintenanceItem value (e.g., "oil_change")
    odometer_miles: float | None = None  # If None, uses cumulative trip miles
    notes: str = ""


@app.get("/api/maintenance/status")
async def maintenance_status() -> JSONResponse:
    """Get maintenance status for all tracked items."""
    if not settings.intelligence_enabled:
        return JSONResponse({"items": [], "error": "intelligence layer disabled"})
    db: RuneDatabase = app.state.db
    tracker: MaintenanceTracker = app.state.maintenance_tracker
    cumulative_miles = await db.get_cumulative_miles()
    statuses = await tracker.check_maintenance(
        current_odometer_miles=cumulative_miles,
        db=db,
        alert_queue=app.state.alert_queue,
    )
    return JSONResponse({
        "items": [s.model_dump() for s in statuses],
        "odometer_miles": round(cumulative_miles, 1),
    })


@app.post("/api/maintenance/done")
async def maintenance_done(req: MaintenanceDoneRequest) -> JSONResponse:
    """Mark a maintenance item as completed."""
    if not settings.intelligence_enabled:
        return JSONResponse({"error": "intelligence layer disabled"}, status_code=503)
    db: RuneDatabase = app.state.db
    tracker: MaintenanceTracker = app.state.maintenance_tracker
    from backend.intelligence.models import MaintenanceItem
    try:
        item = MaintenanceItem(req.item)
    except ValueError:
        return JSONResponse({"error": f"Unknown item: {req.item}"}, status_code=422)
    odometer = req.odometer_miles
    if odometer is None:
        odometer = await db.get_cumulative_miles()
    record = await tracker.mark_done(
        item=item, odometer_miles=odometer, db=db, notes=req.notes,
    )
    return JSONResponse({"ok": True, "record": record.model_dump()})


@app.get("/api/intelligence/status")
async def intelligence_status() -> JSONResponse:
    """Intelligence layer status overview."""
    if not settings.intelligence_enabled:
        return JSONResponse({"enabled": False})
    result: dict[str, Any] = {"enabled": True}
    if app.state.battery_monitor:
        result["battery"] = app.state.battery_monitor.trend.model_dump()
    if app.state.trip_scorer:
        result["baseline_mpg"] = app.state.trip_scorer.get_baseline_mpg()
    if app.state.can_decoder:
        result["can_decoder"] = app.state.can_decoder.get_stats()
    if app.state.cold_start_profiler:
        model = app.state.cold_start_profiler.model
        result["warmup_model"] = model.model_dump() if model else None
    return JSONResponse(result)


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


# Serve built frontend from dist/ (must be LAST -- catches all routes)
# Dev: repo-root/pixel/frontend/dist, Pi: /opt/rune/frontend/dist
_dist_dir = _app_root / "frontend" / "dist"
if not _dist_dir.exists():
    _dist_dir = _app_root.parent / "pixel" / "frontend" / "dist"
if _dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="frontend-dist")
