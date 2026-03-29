"""Rune Sync Engine -- iPhone pull-sync protocol.

Implements the four functions behind the sync API endpoints. The iPhone
hits these when it joins the Rune WiFi AP. The Pi has zero internet;
the iPhone is the relay that pushes alerts to ntfy.sh via cellular.

Protocol flow:
  1. iPhone joins Rune WiFi, iOS Shortcut triggers.
  2. GET /api/sync/status  -> see if anything is pending.
  3. GET /api/sync/alerts  -> grab unsynced alerts (<1KB).
  4. GET /api/sync/delta?since=<iso>  -> get trip summaries + readings count.
  5. POST /api/sync/ack    -> mark alerts synced, advance cursor.

Timestamp boundary: iPhone sends ISO 8601, DB stores Unix ms.
All conversions happen in this module.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from backend.database.db import RuneDatabase

logger = logging.getLogger(__name__)

# sync_state table key for the last successful sync cursor
_CURSOR_KEY = "last_sync_at_iso"


def _iso_to_ms(iso: str) -> int:
    """Parse ISO 8601 string to Unix milliseconds."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)


def _ms_to_iso(ts_ms: int) -> str:
    """Convert Unix milliseconds to ISO 8601 UTC string."""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _now_iso() -> str:
    """Current time as ISO 8601 UTC string."""
    return datetime.now(tz=timezone.utc).isoformat()


async def get_unsynced_alerts(db: RuneDatabase) -> dict[str, Any]:
    """Return all unsynced alerts for iPhone relay. Empty list if none pending."""
    rows = await db.get_unsynced_alerts()
    alerts = []
    for r in rows:
        alerts.append({
            "id": r["id"],
            "ts": _ms_to_iso(r["ts"]),
            "severity": r["severity"],
            "category": r["category"],
            "message": r["message"],
            "data": json.loads(r["data"]) if r.get("data") else None,
        })
    logger.debug("Sync alerts: returning %d unsynced alerts", len(alerts))
    return {
        "alerts": alerts,
        "count": len(alerts),
        "fetched_at": _now_iso(),
    }


async def get_delta(
    db: RuneDatabase,
    since_iso: str,
) -> dict[str, Any]:
    """Return trip summaries + sensor reading count since a timestamp.

    Readings are NOT included in the body (too large for quick sync).
    Only the count is returned so the iPhone can decide whether to trigger
    a full DB export via /api/export. Trips ARE included (small dataset).

    The caller adds X-Rune-Checksum header from the serialized body.
    """
    try:
        since_ms = _iso_to_ms(since_iso)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid since timestamp: {since_iso!r}: {e}") from e

    until_ms = int(time.time() * 1000)

    readings_count = await db.count_readings_since(since_ms)
    trips = await db.get_trips_since(since_ms)

    # Parse trip_stats JSON blob and add ISO timestamps for iPhone
    for t in trips:
        if t.get("trip_stats") and isinstance(t["trip_stats"], str):
            try:
                t["trip_stats"] = json.loads(t["trip_stats"])
            except (ValueError, TypeError):
                t["trip_stats"] = None
        if t.get("start_time"):
            t["start_time_iso"] = _ms_to_iso(t["start_time"])
        if t.get("end_time"):
            t["end_time_iso"] = _ms_to_iso(t["end_time"])

    logger.debug(
        "Sync delta: since=%s readings=%d trips=%d",
        since_iso, readings_count, len(trips),
    )
    return {
        "since_ts": since_iso,
        "until_ts": _ms_to_iso(until_ms),
        "readings_count": readings_count,
        "trips": trips,
        "trips_count": len(trips),
    }


async def ack_sync(
    db: RuneDatabase,
    alert_ids: list[int],
    cursor_iso: str | None = None,
) -> dict[str, Any]:
    """Mark alerts as synced and advance the sync cursor.

    Idempotent: calling multiple times with the same alert_ids is safe.
    cursor_iso: the iPhone's local time after successful ntfy relay.
    If None, server time is used.
    """
    acked_count = 0
    if alert_ids:
        acked_count = await db.ack_alerts(alert_ids)

    # Advance sync cursor -- never regress to an older timestamp
    effective_cursor = cursor_iso if cursor_iso else _now_iso()
    if cursor_iso:
        try:
            new_ms = _iso_to_ms(cursor_iso)
            # Prevent cursor regression (stale iPhone timestamp, retries, clock drift)
            current_cursor = await db.get_sync_value(_CURSOR_KEY)
            if current_cursor:
                try:
                    current_ms = _iso_to_ms(current_cursor)
                    if new_ms < current_ms:
                        logger.warning(
                            "ack_sync: cursor_iso %r is older than current %r, ignoring",
                            cursor_iso, current_cursor,
                        )
                        effective_cursor = current_cursor
                except ValueError:
                    pass  # Current cursor is corrupt, overwrite it
        except ValueError:
            logger.warning(
                "ack_sync: invalid cursor_iso %r, using server time", cursor_iso,
            )
            effective_cursor = _now_iso()

    await db.set_sync_value(_CURSOR_KEY, effective_cursor)

    logger.info(
        "Sync ack: %d alerts marked synced, cursor advanced to %s",
        acked_count, effective_cursor,
    )
    return {
        "acked": acked_count,
        "cursor": effective_cursor,
        "ok": True,
    }


async def get_sync_status(db: RuneDatabase) -> dict[str, Any]:
    """Current sync state snapshot for the iPhone to poll on connect."""
    last_sync_iso = await db.get_sync_value(_CURSOR_KEY)

    unsynced = await db.get_unsynced_alerts()
    pending_alerts = len(unsynced)

    readings_since = 0
    if last_sync_iso:
        try:
            since_ms = _iso_to_ms(last_sync_iso)
            readings_since = await db.count_readings_since(since_ms)
        except ValueError:
            logger.warning("sync_status: bad cursor in DB: %r", last_sync_iso)
            readings_since = -1

    return {
        "pending_alerts": pending_alerts,
        "last_sync_at": last_sync_iso,
        "readings_since_sync": readings_since,
        "server_time": _now_iso(),
        "has_data": pending_alerts > 0 or readings_since > 0,
    }
