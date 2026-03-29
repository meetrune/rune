"""Manual control actions for the Rune diagnostics dashboard.

These endpoints let the engineer trigger maintenance operations
from the browser instead of SSH-ing into the Pi.

All actions return structured results with timing information.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


async def force_checkpoint(db: Any) -> dict[str, Any]:
    """Force a WAL checkpoint and return the result.

    WAL mode accumulates writes in a separate file. Checkpointing
    transfers those writes to the main DB file. SQLite does this
    automatically, but sometimes you want to force it (e.g., before
    copying the DB file for offline analysis).

    Delegates to RuneDatabase.force_checkpoint() -- no private access.
    """
    t = time.monotonic()
    try:
        ckpt = await db.force_checkpoint()
        elapsed = (time.monotonic() - t) * 1000
        result = {
            "success": True,
            "busy": ckpt["busy"],
            "log_pages": ckpt["log_pages"],
            "checkpointed_pages": ckpt["checkpointed_pages"],
            "duration_ms": round(elapsed, 2),
        }
        logger.info(
            "Manual WAL checkpoint: %d pages checkpointed in %.1fms",
            result["checkpointed_pages"], elapsed,
        )
        return result
    except Exception as e:
        elapsed = (time.monotonic() - t) * 1000
        logger.error("Manual WAL checkpoint failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "duration_ms": round(elapsed, 2),
        }


async def recalibrate_health_scorer(scorer: Any) -> dict[str, Any]:
    """Reopen the health scorer's calibration gate.

    Resets the sample counter and calibration flag, causing the scorer
    to return -1 (calibrating) for approximately 5 minutes.

    NOTE: This does NOT reset the HalfSpaceTrees anomaly model or EWMA
    smoothers. The learned baseline persists. If bad sensor data was
    ingested into the HST, a full restart is needed to flush it.
    """
    t = time.monotonic()
    try:
        old_samples = scorer.sample_count
        scorer.reset_calibration()
        elapsed = (time.monotonic() - t) * 1000
        logger.info(
            "Health scorer recalibrated (was at %d samples, now reset to 0)",
            old_samples,
        )
        return {
            "success": True,
            "previous_sample_count": old_samples,
            "duration_ms": round(elapsed, 2),
            "message": "Calibration gate reopened. Scores will show -1 for ~5 minutes. Anomaly model retained.",
        }
    except Exception as e:
        elapsed = (time.monotonic() - t) * 1000
        logger.error("Health scorer recalibration failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "duration_ms": round(elapsed, 2),
        }


async def go_live(
    db: Any,
    scorer: Any,
    go_live_event: asyncio.Event,
    use_simulator: bool = True,
) -> dict[str, Any]:
    """Switch from simulation to real OBD. One-way operation.

    1. Purge all simulated data from the database
    2. Reset the health scorer so it recalibrates on real data
    3. Signal the producer loop to swap SimulatedCollector for OBDCollector

    To revert to simulation mode, restart the server with
    RUNE_USE_SIMULATOR=true.
    """
    t = time.monotonic()
    try:
        # Guard: cannot go live if already live
        if not use_simulator:
            return {
                "success": False,
                "error": "Already in live mode. Cannot purge real data.",
                "duration_ms": 0.0,
            }

        # Purge all simulated data
        purged = await db.purge_all()

        # Clear in-memory log buffer (old simulator logs)
        from backend.api.logs import log_buffer
        log_buffer.clear()

        # Reset health scorer for fresh calibration on real data
        scorer.reset_calibration()

        # Signal the producer loop to swap collectors
        go_live_event.set()

        elapsed = (time.monotonic() - t) * 1000
        logger.warning(
            "GO LIVE: purged %s, health scorer reset, collector swap signaled (%.1fms)",
            purged, elapsed,
        )
        return {
            "success": True,
            "status": "live",
            "purged": purged,
            "health_scorer": "recalibrating",
            "collector": "swapping_to_obd",
            "duration_ms": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = (time.monotonic() - t) * 1000
        logger.error("Go live failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "duration_ms": round(elapsed, 2),
        }


async def reset_all_data(
    db: Any,
    scorer: Any,
) -> dict[str, Any]:
    """Wipe all stored data and reset calibration. Works in any mode.

    Use this after hardware testing to start fresh before daily driving.
    Does NOT change the collector mode (sim vs live stays as-is).
    """
    t = time.monotonic()
    try:
        purged = await db.purge_all()

        # Clear in-memory log buffer
        from backend.api.logs import log_buffer
        log_buffer.clear()

        # Reset health scorer so it recalibrates from scratch
        scorer.reset_calibration()

        elapsed = (time.monotonic() - t) * 1000
        logger.warning(
            "RESET ALL DATA: purged %s, logs cleared, health scorer reset (%.1fms)",
            purged, elapsed,
        )
        return {
            "success": True,
            "purged": purged,
            "logs": "cleared",
            "health_scorer": "recalibrating",
            "duration_ms": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = (time.monotonic() - t) * 1000
        logger.error("Reset all data failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "duration_ms": round(elapsed, 2),
        }
