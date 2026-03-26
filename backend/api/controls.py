"""Manual control actions for the Rune diagnostics dashboard.

These endpoints let the engineer trigger maintenance operations
from the browser instead of SSH-ing into the Pi.

All actions return structured results with timing information.
"""

from __future__ import annotations

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
