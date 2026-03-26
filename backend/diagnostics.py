"""Rune system diagnostics.

Runs comprehensive checks on every component in the pipeline
and returns structured results for the diagnostic dashboard.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""
    name: str
    category: str
    status: str  # "pass", "fail", "warn", "skip"
    message: str
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "details": self.details,
        }


async def run_all_checks(app_state: Any) -> list[CheckResult]:
    """Run all diagnostic checks against the running application."""
    results: list[CheckResult] = []

    # --- Backend Core ---
    results.append(await _check_server(app_state))
    results.append(await _check_database(app_state))
    results.append(await _check_collector(app_state))
    results.append(await _check_fuel_calc(app_state))
    results.append(await _check_health_scorer(app_state))
    results.append(await _check_thermal_manager(app_state))
    results.append(await _check_wittypi_reader(app_state))
    results.append(await _check_websocket_manager(app_state))

    # --- Data Pipeline ---
    results.append(await _check_snapshot_generation(app_state))
    results.append(await _check_fuel_pipeline(app_state))
    results.append(await _check_health_pipeline(app_state))
    results.append(await _check_db_write_read(app_state))

    # --- Deploy Files ---
    results.extend(_check_deploy_files())

    # --- Frontend ---
    results.extend(_check_frontend_build())

    return results


async def _check_server(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        from backend.config import settings
        return CheckResult(
            name="FastAPI Server",
            category="backend",
            status="pass",
            message=f"Running. Simulator={settings.use_simulator}, WS rate={settings.ws_rate_hz}Hz",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"simulator": settings.use_simulator, "ws_rate_hz": settings.ws_rate_hz},
        )
    except Exception as e:
        return CheckResult(
            name="FastAPI Server", category="backend",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_database(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        db = state.db
        counts = await db.get_table_counts()
        size = await db.get_db_size_bytes()
        return CheckResult(
            name="SQLite Database",
            category="backend",
            status="pass",
            message=f"{sum(counts.values())} total rows, {size / 1024:.1f}KB",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"tables": counts, "size_bytes": size},
        )
    except Exception as e:
        return CheckResult(
            name="SQLite Database", category="backend",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_collector(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        collector = state.collector
        running = collector.is_running
        ctype = type(collector).__name__
        return CheckResult(
            name="OBD Collector",
            category="backend",
            status="pass" if running else "warn",
            message=f"{ctype}, running={running}",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"type": ctype, "running": running},
        )
    except Exception as e:
        return CheckResult(
            name="OBD Collector", category="backend",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_fuel_calc(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        fc = state.fuel_calc
        trip_active = fc.is_trip_active
        return CheckResult(
            name="Fuel Calculator",
            category="backend",
            status="pass",
            message=f"Active trip: {trip_active}",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"trip_active": trip_active},
        )
    except Exception as e:
        return CheckResult(
            name="Fuel Calculator", category="backend",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_health_scorer(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        hs = state.health_scorer
        debug = hs.get_debug_state()
        calibrated = debug.get("calibration_complete", False)
        return CheckResult(
            name="Health Scorer",
            category="backend",
            status="pass" if calibrated else "warn",
            message="Calibrated" if calibrated else "Calibrating (need ~5 min of data)",
            duration_ms=(time.monotonic() - t) * 1000,
            details=debug,
        )
    except Exception as e:
        return CheckResult(
            name="Health Scorer", category="backend",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_thermal_manager(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        tm = state.thermal_mgr
        debug = tm.get_debug_state()
        return CheckResult(
            name="Thermal Manager",
            category="backend",
            status="pass",
            message=f"CPU={debug['cpu_status']}, armrest={debug['armrest_status']}",
            duration_ms=(time.monotonic() - t) * 1000,
            details=debug,
        )
    except Exception as e:
        return CheckResult(
            name="Thermal Manager", category="backend",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_wittypi_reader(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        pr = state.pi_reader
        available = pr.is_available
        ctype = type(pr).__name__
        status = "pass" if available else "warn"
        msg = f"{ctype}, available={available}"
        if not available and "Simulated" not in ctype:
            msg += " (I2C not connected -- expected on Mac)"
        return CheckResult(
            name="Witty Pi Reader",
            category="sensors",
            status=status,
            message=msg,
            duration_ms=(time.monotonic() - t) * 1000,
            details={"type": ctype, "available": available},
        )
    except Exception as e:
        return CheckResult(
            name="Witty Pi Reader", category="sensors",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_websocket_manager(state: Any) -> CheckResult:
    t = time.monotonic()
    try:
        mgr = state.connection_manager
        count = mgr.client_count
        return CheckResult(
            name="WebSocket Manager",
            category="backend",
            status="pass",
            message=f"{count} client(s) connected",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"clients": count},
        )
    except Exception as e:
        return CheckResult(
            name="WebSocket Manager", category="backend",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_snapshot_generation(state: Any) -> CheckResult:
    """Test that the collector can generate a snapshot."""
    t = time.monotonic()
    try:
        collector = state.collector
        snap = await collector.get_snapshot()
        fields_set = sum(1 for f in ["rpm", "speed_kph", "coolant_temp_c", "maf_gps",
                                      "battery_voltage", "fuel_level_pct"]
                         if getattr(snap, f, 0) != 0)
        return CheckResult(
            name="Snapshot Generation",
            category="pipeline",
            status="pass" if fields_set >= 3 else "warn",
            message=f"RPM={snap.rpm:.0f}, speed={snap.speed_kph:.0f}kph, coolant={snap.coolant_temp_c:.1f}C, {fields_set}/6 core fields populated",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"rpm": snap.rpm, "speed_kph": snap.speed_kph, "coolant_c": snap.coolant_temp_c},
        )
    except Exception as e:
        return CheckResult(
            name="Snapshot Generation", category="pipeline",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_fuel_pipeline(state: Any) -> CheckResult:
    """Test that fuel calculation works on a snapshot."""
    t = time.monotonic()
    try:
        collector = state.collector
        fc = state.fuel_calc
        snap = await collector.get_snapshot()
        fuel_snap, _, _ = fc.update(snap)
        mpg_str = f"{fuel_snap.instant_mpg:.1f}" if fuel_snap.instant_mpg is not None else "idle"
        return CheckResult(
            name="Fuel Pipeline",
            category="pipeline",
            status="pass",
            message=f"instant_mpg={mpg_str}, trip_dist={fuel_snap.trip_distance_mi:.2f}mi",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"instant_mpg": fuel_snap.instant_mpg, "trip_distance_mi": fuel_snap.trip_distance_mi},
        )
    except Exception as e:
        return CheckResult(
            name="Fuel Pipeline", category="pipeline",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_health_pipeline(state: Any) -> CheckResult:
    """Test that health scoring works on a snapshot."""
    t = time.monotonic()
    try:
        collector = state.collector
        hs = state.health_scorer
        snap = await collector.get_snapshot()
        health = hs.score(snap)
        return CheckResult(
            name="Health Pipeline",
            category="pipeline",
            status="pass" if health.overall != -1 else "warn",
            message=f"overall={health.overall:.0f}" if health.overall != -1 else "Calibrating (-1)",
            duration_ms=(time.monotonic() - t) * 1000,
            details={"overall": health.overall, "engine": health.engine, "electrical": health.electrical},
        )
    except Exception as e:
        return CheckResult(
            name="Health Pipeline", category="pipeline",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


async def _check_db_write_read(state: Any) -> CheckResult:
    """Test that DB write + read cycle works."""
    t = time.monotonic()
    try:
        db = state.db
        collector = state.collector
        snap = await collector.get_snapshot()
        await db.insert_reading(snap)
        counts = await db.get_table_counts()
        return CheckResult(
            name="DB Write/Read Cycle",
            category="pipeline",
            status="pass",
            message=f"Write succeeded, {counts.get('sensor_readings', 0)} readings in DB",
            duration_ms=(time.monotonic() - t) * 1000,
            details=counts,
        )
    except Exception as e:
        return CheckResult(
            name="DB Write/Read Cycle", category="pipeline",
            status="fail", message=str(e),
            duration_ms=(time.monotonic() - t) * 1000,
        )


def _check_deploy_files() -> list[CheckResult]:
    """Check all deployment files exist and are valid."""
    results = []
    base = Path(__file__).parent.parent / "deploy"

    files = {
        "setup.sh": ("deploy", "Pi setup script"),
        "rune.service": ("deploy", "systemd service"),
        "rune.env": ("deploy", "production environment"),
        "rune-shutdown.sh": ("deploy", "graceful shutdown hook"),
        "wittypi-setup.sh": ("deploy", "Witty Pi I2C config"),
    }

    for filename, (category, desc) in files.items():
        path = base / filename
        if path.exists():
            size = path.stat().st_size
            executable = os.access(path, os.X_OK) if filename.endswith(".sh") else True
            status = "pass" if (size > 0 and executable) else "warn"
            msg = f"{desc} ({size}B)"
            if filename.endswith(".sh") and not executable:
                msg += " -- NOT EXECUTABLE"
                status = "warn"
            results.append(CheckResult(name=filename, category=category, status=status, message=msg))
        else:
            results.append(CheckResult(name=filename, category=category, status="fail", message=f"MISSING: {desc}"))

    # CI pipeline
    ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
    if ci_path.exists():
        results.append(CheckResult(name="ci.yml", category="deploy", status="pass", message="GitHub Actions CI pipeline"))
    else:
        results.append(CheckResult(name="ci.yml", category="deploy", status="warn", message="No CI pipeline"))

    return results


def _check_frontend_build() -> list[CheckResult]:
    """Check frontend build artifacts."""
    results = []
    base = Path(__file__).parent.parent / "frontend"

    # Package.json
    pkg = base / "package.json"
    if pkg.exists():
        results.append(CheckResult(name="package.json", category="frontend", status="pass", message="Frontend dependencies defined"))
    else:
        results.append(CheckResult(name="package.json", category="frontend", status="fail", message="MISSING"))

    # Built dist
    dist = base / "dist"
    if dist.exists():
        index = dist / "index.html"
        sw = dist / "sw.js"
        results.append(CheckResult(
            name="Frontend Build (dist/)",
            category="frontend",
            status="pass" if index.exists() else "fail",
            message="Built" if index.exists() else "dist/ exists but no index.html",
            details={"has_sw": sw.exists()},
        ))
        if sw.exists():
            results.append(CheckResult(name="Service Worker (sw.js)", category="frontend", status="pass", message="PWA service worker present"))
        else:
            results.append(CheckResult(name="Service Worker (sw.js)", category="frontend", status="warn", message="No service worker -- run npm build"))
    else:
        results.append(CheckResult(name="Frontend Build (dist/)", category="frontend", status="warn", message="Not built yet -- run cd frontend && npm run build"))

    # 3D model
    model = base / "public" / "models" / "accord.glb"
    if model.exists():
        size_mb = model.stat().st_size / (1024 * 1024)
        results.append(CheckResult(name="3D Car Model (accord.glb)", category="frontend", status="pass", message=f"{size_mb:.1f}MB"))
    else:
        results.append(CheckResult(name="3D Car Model (accord.glb)", category="frontend", status="fail", message="MISSING -- 3D telemetry screen won't render"))

    # Manifest + icons
    manifest = base / "public" / "manifest.json"
    results.append(CheckResult(
        name="PWA Manifest",
        category="frontend",
        status="pass" if manifest.exists() else "warn",
        message="Present" if manifest.exists() else "Missing manifest.json",
    ))

    return results
