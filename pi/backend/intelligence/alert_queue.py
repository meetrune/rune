"""Rune Alert Queue -- rate-limited alert writer for the intelligence layer.

Other intelligence features call alert_queue.enqueue() to raise an alert.
This class enforces a per-category rate limit (default 1 per hour) so a
runaway sensor loop cannot flood the alert_queue table with 10Hz duplicates.

The DB alert_queue table IS the queue -- no in-memory buffering needed.
Alerts survive Pi restarts. Rate limit state is in-memory (resets on restart,
which is acceptable since restarts are rare and the first alert per category
after restart is always allowed through).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from backend.database.db import RuneDatabase
from backend.intelligence.models import AlertCategory, AlertSeverity

logger = logging.getLogger(__name__)


class AlertQueue:
    """Rate-limited bridge between intelligence features and the DB alert table."""

    def __init__(
        self,
        db: RuneDatabase,
        rate_limit_seconds: float = 3600.0,
    ) -> None:
        self._db = db
        self._rate_limit_s = rate_limit_seconds
        # Maps category value -> epoch seconds of last successful enqueue
        self._last_enqueue: dict[str, float] = {}
        # Suppressed count per category since last successful enqueue
        self._suppressed: dict[str, int] = {}
        # Lock to prevent TOCTOU race on rate limit check-then-insert
        self._lock = asyncio.Lock()

    async def enqueue(
        self,
        severity: AlertSeverity,
        category: AlertCategory,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> int | None:
        """Queue an alert for iPhone sync.

        Returns the new alert_id (int) if queued.
        Returns None if suppressed by rate limit.
        """
        cat_key = category.value

        # Lock prevents TOCTOU race: two coroutines checking rate limit
        # concurrently could both pass before either updates _last_enqueue
        async with self._lock:
            now = time.time()
            last = self._last_enqueue.get(cat_key, 0.0)

            if (now - last) < self._rate_limit_s:
                self._suppressed[cat_key] = self._suppressed.get(cat_key, 0) + 1
                logger.debug(
                    "Alert suppressed by rate limit: category=%s suppressed_count=%d",
                    cat_key,
                    self._suppressed[cat_key],
                )
                return None

            # Mark rate limit before DB insert so concurrent calls are blocked
            self._last_enqueue[cat_key] = now

        # DB insert outside the lock -- other categories can proceed
        data_json: str | None = json.dumps(data) if data is not None else None
        try:
            alert_id = await self._db.insert_alert(
                severity=severity.value,
                category=cat_key,
                message=message,
                data=data_json,
            )
        except Exception:
            logger.exception("AlertQueue: DB insert failed for category=%s", cat_key)
            # Revert rate limit on failure so the next attempt can try again
            async with self._lock:
                self._last_enqueue[cat_key] = 0.0
            return None

        async with self._lock:
            suppressed = self._suppressed.pop(cat_key, 0)
        if suppressed:
            logger.info(
                "Alert queued: category=%s severity=%s (suppressed %d duplicates)",
                cat_key, severity.value, suppressed,
            )
        else:
            logger.info(
                "Alert queued: id=%d category=%s severity=%s",
                alert_id, cat_key, severity.value,
            )
        return alert_id
