"""Rune's SQLite database layer.

Stores sensor readings, trips, fill-ups, and health scores using
SQLite in WAL mode via aiosqlite. Single shared connection -- aiosqlite
maintainers explicitly rejected connection pooling (issue #163).

Key decisions based on research:
- INTEGER timestamps (Unix milliseconds) -- smaller and faster than REAL
- No AUTOINCREMENT -- 2x insert speed with plain INTEGER PRIMARY KEY
- WAL mode with synchronous=NORMAL -- safe on SD cards, 2x faster than FULL
- Batch writes with executemany -- buffer 1 second, flush together
- wal_autocheckpoint=500 for write-heavy workload (not default 1000)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import shutil
import sqlite3

import aiosqlite

from backend.obd_manager.models import HealthSnapshot, VehicleSnapshot

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id              INTEGER PRIMARY KEY,
    ts              INTEGER NOT NULL,
    rpm             REAL NOT NULL,
    speed_kph       REAL NOT NULL,
    coolant_c       REAL NOT NULL,
    engine_load     REAL NOT NULL,
    maf_gps         REAL NOT NULL,
    stft_pct        REAL NOT NULL,
    ltft_pct        REAL NOT NULL,
    fuel_lvl        REAL NOT NULL,
    catalyst_c      REAL NOT NULL,
    oil_c           REAL NOT NULL,
    battery_v       REAL NOT NULL,
    throttle_pct    REAL NOT NULL DEFAULT 0,
    intake_temp_c   REAL NOT NULL DEFAULT 0,
    intake_map_kpa  REAL NOT NULL DEFAULT 0,
    vin_voltage     REAL,
    armrest_temp_c  REAL,
    pi_cpu_temp_c   REAL,
    pi_current_a    REAL
);
CREATE INDEX IF NOT EXISTS idx_readings_ts ON sensor_readings(ts);

CREATE TABLE IF NOT EXISTS trips (
    trip_id         INTEGER PRIMARY KEY,
    start_time      INTEGER NOT NULL,
    end_time        INTEGER,
    distance_miles  REAL NOT NULL DEFAULT 0,
    fuel_gallons    REAL NOT NULL DEFAULT 0,
    fuel_cost_usd   REAL NOT NULL DEFAULT 0,
    avg_mpg         REAL,
    eco_score       REAL,
    trip_stats      TEXT
);

CREATE TABLE IF NOT EXISTS fillups (
    id                  INTEGER PRIMARY KEY,
    detected_at         INTEGER NOT NULL,
    fuel_level_before   REAL NOT NULL,
    fuel_level_after    REAL NOT NULL,
    estimated_gallons   REAL NOT NULL,
    cost_usd            REAL,
    mpg_since_last_fill REAL
);

CREATE TABLE IF NOT EXISTS health_scores (
    id           INTEGER PRIMARY KEY,
    ts           INTEGER NOT NULL,
    overall      REAL NOT NULL,
    engine       REAL NOT NULL,
    transmission REAL NOT NULL,
    fuel         REAL NOT NULL,
    cooling      REAL NOT NULL,
    exhaust      REAL NOT NULL,
    electrical   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_health_ts ON health_scores(ts);

CREATE TABLE IF NOT EXISTS can_frames (
    id              INTEGER PRIMARY KEY,
    ts              INTEGER NOT NULL,
    can_id          INTEGER NOT NULL,
    dlc             INTEGER NOT NULL,
    data            BLOB NOT NULL,
    bus             INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_can_ts ON can_frames(ts);
CREATE INDEX IF NOT EXISTS idx_can_id ON can_frames(can_id);

-- Intelligence Layer tables (added in feat/rune-intelligence)

CREATE TABLE IF NOT EXISTS alert_queue (
    id              INTEGER PRIMARY KEY,
    ts              INTEGER NOT NULL,
    severity        TEXT NOT NULL,
    category        TEXT NOT NULL,
    message         TEXT NOT NULL,
    data            TEXT,
    synced          INTEGER NOT NULL DEFAULT 0,
    synced_at       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_alert_synced ON alert_queue(synced);
CREATE INDEX IF NOT EXISTS idx_alert_ts ON alert_queue(ts);

CREATE TABLE IF NOT EXISTS sync_state (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_log (
    id              INTEGER PRIMARY KEY,
    item            TEXT NOT NULL,
    done_at         INTEGER NOT NULL,
    odometer_miles  REAL NOT NULL,
    next_due_miles  REAL NOT NULL,
    notes           TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_maint_item ON maintenance_log(item);

CREATE TABLE IF NOT EXISTS can_signals (
    id              INTEGER PRIMARY KEY,
    ts              INTEGER NOT NULL,
    signal_name     TEXT NOT NULL,
    value           REAL NOT NULL,
    unit            TEXT
);
CREATE INDEX IF NOT EXISTS idx_cansig_ts ON can_signals(ts);
CREATE INDEX IF NOT EXISTS idx_cansig_name ON can_signals(signal_name);

CREATE TABLE IF NOT EXISTS cold_starts (
    id              INTEGER PRIMARY KEY,
    trip_id         INTEGER,
    ambient_temp_c  REAL,
    start_coolant_c REAL,
    target_coolant_c REAL DEFAULT 80.0,
    warmup_seconds  REAL,
    ts              INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_coldstart_ts ON cold_starts(ts);
"""

_PRAGMAS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA cache_size=-8000",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA mmap_size=30000000",
    "PRAGMA wal_autocheckpoint=500",
    "PRAGMA journal_size_limit=67108864",
]


def _ts_ms() -> int:
    """Current time as Unix milliseconds."""
    return int(time.time() * 1000)


class RuneDatabase:
    """Async SQLite database for Rune's persistent storage."""

    def __init__(self, db_path: str = "rune.db") -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def db_path(self) -> str:
        """Public access to the database file path."""
        return self._db_path

    async def initialize(self) -> None:
        """Open connection, set pragmas, create tables."""
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        for pragma in _PRAGMAS:
            await self._conn.execute(pragma)

        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        logger.info("Database initialized: %s", self._db_path)

    async def close(self) -> None:
        """Checkpoint WAL and close connection."""
        if self._conn is not None:
            try:
                await self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                logger.warning("WAL checkpoint failed on close", exc_info=True)
            await self._conn.close()
            self._conn = None
            logger.info("Database closed")

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._conn

    # --- sensor_readings ---

    async def insert_reading(self, snap: VehicleSnapshot) -> None:
        """Insert a single sensor reading."""
        conn = self._require_conn()
        await conn.execute(
            """INSERT INTO sensor_readings
               (ts, rpm, speed_kph, coolant_c, engine_load, maf_gps,
                stft_pct, ltft_pct, fuel_lvl, catalyst_c, oil_c, battery_v,
                throttle_pct, intake_temp_c, intake_map_kpa,
                vin_voltage, armrest_temp_c, pi_cpu_temp_c, pi_current_a)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(snap.timestamp * 1000), snap.rpm, snap.speed_kph,
                snap.coolant_temp_c, snap.engine_load_pct, snap.maf_gps,
                snap.stft_pct, snap.ltft_pct, snap.fuel_level_pct,
                snap.catalyst_temp_c, snap.oil_temp_c, snap.battery_voltage,
                snap.throttle_pct, snap.intake_air_temp_c, snap.intake_manifold_kpa,
                snap.vin_voltage, snap.armrest_temp_c, snap.pi_cpu_temp_c, snap.pi_current_a,
            ),
        )
        await conn.commit()

    async def insert_readings(self, snaps: list[VehicleSnapshot]) -> None:
        """Batch insert sensor readings (use for 1-second buffer flush)."""
        if not snaps:
            return
        conn = self._require_conn()
        rows = [
            (
                int(s.timestamp * 1000), s.rpm, s.speed_kph,
                s.coolant_temp_c, s.engine_load_pct, s.maf_gps,
                s.stft_pct, s.ltft_pct, s.fuel_level_pct,
                s.catalyst_temp_c, s.oil_temp_c, s.battery_voltage,
                s.throttle_pct, s.intake_air_temp_c, s.intake_manifold_kpa,
                s.vin_voltage, s.armrest_temp_c, s.pi_cpu_temp_c, s.pi_current_a,
            )
            for s in snaps
        ]
        await conn.executemany(
            """INSERT INTO sensor_readings
               (ts, rpm, speed_kph, coolant_c, engine_load, maf_gps,
                stft_pct, ltft_pct, fuel_lvl, catalyst_c, oil_c, battery_v,
                throttle_pct, intake_temp_c, intake_map_kpa,
                vin_voltage, armrest_temp_c, pi_cpu_temp_c, pi_current_a)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await conn.commit()

    # --- trips ---

    async def start_trip(self, start_time_ms: int) -> int:
        """Insert a new trip and return its trip_id."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "INSERT INTO trips (start_time) VALUES (?)",
            (start_time_ms,),
        )
        await conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to create trip -- no lastrowid returned")
        return cursor.lastrowid

    async def end_trip(
        self,
        trip_id: int,
        end_time_ms: int,
        distance_miles: float,
        fuel_gallons: float,
        fuel_cost_usd: float,
        avg_mpg: float | None,
        trip_stats: str | None = None,
    ) -> None:
        """Finalize a trip with end time, totals, and rich stats JSON."""
        conn = self._require_conn()
        await conn.execute(
            """UPDATE trips SET end_time=?, distance_miles=?, fuel_gallons=?,
               fuel_cost_usd=?, avg_mpg=?, trip_stats=? WHERE trip_id=?""",
            (end_time_ms, distance_miles, fuel_gallons, fuel_cost_usd, avg_mpg, trip_stats, trip_id),
        )
        await conn.commit()

    async def get_trip(self, trip_id: int) -> dict[str, Any] | None:
        """Get a trip by ID."""
        conn = self._require_conn()
        cursor = await conn.execute("SELECT * FROM trips WHERE trip_id=?", (trip_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_recent_trips(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the most recent trips."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM trips ORDER BY start_time DESC LIMIT ?", (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # --- fillups ---

    async def insert_fillup(
        self,
        detected_at_ms: int,
        fuel_level_before: float,
        fuel_level_after: float,
        estimated_gallons: float,
        cost_usd: float | None = None,
        mpg_since_last_fill: float | None = None,
    ) -> None:
        """Record a fill-up event."""
        conn = self._require_conn()
        await conn.execute(
            """INSERT INTO fillups
               (detected_at, fuel_level_before, fuel_level_after,
                estimated_gallons, cost_usd, mpg_since_last_fill)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (detected_at_ms, fuel_level_before, fuel_level_after,
             estimated_gallons, cost_usd, mpg_since_last_fill),
        )
        await conn.commit()

    async def get_last_fillup(self) -> dict[str, Any] | None:
        """Get the most recent fill-up event."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM fillups ORDER BY detected_at DESC LIMIT 1",
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # --- health_scores ---

    async def insert_health_score(self, ts_ms: int, health: HealthSnapshot) -> None:
        """Store a health score snapshot."""
        conn = self._require_conn()
        await conn.execute(
            """INSERT INTO health_scores
               (ts, overall, engine, transmission, fuel, cooling, exhaust, electrical)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts_ms, health.overall, health.engine, health.transmission,
             health.fuel, health.cooling, health.exhaust, health.electrical),
        )
        await conn.commit()

    async def get_health_trend(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get health scores from the last N hours."""
        conn = self._require_conn()
        cutoff = _ts_ms() - (hours * 3600 * 1000)
        cursor = await conn.execute(
            "SELECT * FROM health_scores WHERE ts > ? ORDER BY ts ASC",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # --- table counts ---

    async def get_table_counts(self) -> dict[str, int]:
        """Return row counts for all 4 tables."""
        conn = self._require_conn()
        counts: dict[str, int] = {}
        for table in (
            "sensor_readings", "trips", "fillups", "health_scores", "can_frames",
            "alert_queue", "sync_state", "maintenance_log", "can_signals", "cold_starts",
        ):
            cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            row = await cursor.fetchone()
            counts[table] = row[0] if row else 0
        return counts

    # --- maintenance ---

    async def cleanup(self, retention_days: int = 90) -> dict[str, int]:
        """Delete old data and reclaim space.

        Keeps the last retention_days of sensor readings.
        Removes trips with zero meaningful distance (false starts from noise).
        Checkpoints and vacuums the WAL file.

        Returns counts of deleted rows per table.
        """
        conn = self._require_conn()
        cutoff = _ts_ms() - (retention_days * 86400 * 1000)
        deleted: dict[str, int] = {}

        # Old sensor readings
        cursor = await conn.execute(
            "DELETE FROM sensor_readings WHERE ts < ?", (cutoff,),
        )
        deleted["sensor_readings"] = cursor.rowcount or 0

        # Old health scores
        cursor = await conn.execute(
            "DELETE FROM health_scores WHERE ts < ?", (cutoff,),
        )
        deleted["health_scores"] = cursor.rowcount or 0

        # Old CAN frames
        cursor = await conn.execute(
            "DELETE FROM can_frames WHERE ts < ?", (cutoff,),
        )
        deleted["can_frames"] = cursor.rowcount or 0

        # Junk trips: completed trips with < 0.01 miles (noise-triggered false starts)
        cursor = await conn.execute(
            "DELETE FROM trips WHERE end_time IS NOT NULL AND distance_miles < 0.01",
        )
        deleted["junk_trips"] = cursor.rowcount or 0

        await conn.commit()

        # Reclaim disk space -- VACUUM rewrites the DB file (works with any auto_vacuum mode)
        await conn.execute("VACUUM")
        await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await conn.commit()

        logger.info(
            "Cleanup: deleted %d readings, %d health scores, %d junk trips",
            deleted["sensor_readings"], deleted["health_scores"], deleted["junk_trips"],
        )
        return deleted

    async def get_db_size_bytes(self) -> int:
        """Get total DB file size (main + WAL + SHM)."""
        total = 0
        for suffix in ("", "-wal", "-shm"):
            path = self._db_path + suffix
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
        return total

    def get_wal_size_bytes(self) -> int:
        """Get WAL file size. 0 if WAL doesn't exist or is empty."""
        try:
            return os.path.getsize(self._db_path + "-wal")
        except OSError:
            return 0

    async def force_checkpoint(self) -> dict[str, int]:
        """Force a WAL checkpoint (TRUNCATE mode).

        Returns (busy, log_pages, checkpointed_pages).
        """
        conn = self._require_conn()
        cursor = await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        row = await cursor.fetchone()
        return {
            "busy": row[0] if row else 0,
            "log_pages": row[1] if row else 0,
            "checkpointed_pages": row[2] if row else 0,
        }

    async def get_insert_rate(self, window_seconds: int = 60) -> float:
        """Estimate insert rate (readings/sec) over the last N seconds."""
        conn = self._require_conn()
        cutoff = _ts_ms() - (window_seconds * 1000)
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM sensor_readings WHERE ts > ?", (cutoff,),
        )
        row = await cursor.fetchone()
        count = row[0] if row else 0
        return round(count / window_seconds, 1) if window_seconds > 0 else 0.0

    # --- can_frames ---

    async def insert_can_frames(self, frames: list[object]) -> None:
        """Batch insert raw CAN frames from the CANListener.

        Args:
            frames: list of CANFrame dataclass instances with
                    timestamp_ms, can_id, dlc, data (bytes), bus fields.
        """
        if not frames:
            return
        conn = self._require_conn()
        rows = [
            (f.timestamp_ms, f.can_id, f.dlc, f.data, f.bus)  # type: ignore[attr-defined]
            for f in frames
        ]
        await conn.executemany(
            """INSERT INTO can_frames (ts, can_id, dlc, data, bus)
               VALUES (?, ?, ?, ?, ?)""",
            rows,
        )
        await conn.commit()

    # --- backup (for /api/export) ---

    async def backup(self, dest_path: str) -> str:
        """Create a safe SQLite backup for export.

        Uses SQLite's backup API via a separate synchronous connection
        so the live WAL-mode DB is not locked during the copy.
        Returns the destination path.
        """
        conn = self._require_conn()
        # Checkpoint WAL first so backup includes latest writes
        await conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

        def _do_backup() -> None:
            src = sqlite3.connect(self._db_path)
            dst = sqlite3.connect(dest_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()

        await asyncio.to_thread(_do_backup)
        logger.info("Database backup created: %s", dest_path)
        return dest_path

    # --- purge ---

    # --- Intelligence Layer: alert_queue ---

    async def insert_alert(
        self,
        severity: str,
        category: str,
        message: str,
        data: str | None = None,
    ) -> int:
        """Queue an alert for iPhone sync relay."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """INSERT INTO alert_queue (ts, severity, category, message, data)
               VALUES (?, ?, ?, ?, ?)""",
            (_ts_ms(), severity, category, message, data),
        )
        await conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("insert_alert returned no lastrowid -- insert may have silently failed")
        return cursor.lastrowid

    async def get_unsynced_alerts(self) -> list[dict[str, Any]]:
        """Get all alerts not yet synced to iPhone."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM alert_queue WHERE synced = 0 ORDER BY ts ASC",
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def ack_alerts(self, alert_ids: list[int]) -> int:
        """Mark alerts as synced. Idempotent -- safe to call multiple times."""
        if not alert_ids:
            return 0
        conn = self._require_conn()
        placeholders = ",".join("?" for _ in alert_ids)
        now = _ts_ms()
        cursor = await conn.execute(
            f"UPDATE alert_queue SET synced = 1, synced_at = ? WHERE id IN ({placeholders})",  # noqa: S608
            [now, *alert_ids],
        )
        await conn.commit()
        return cursor.rowcount or 0

    # --- Intelligence Layer: sync_state ---

    async def get_sync_value(self, key: str) -> str | None:
        """Get a sync state value by key."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT value FROM sync_state WHERE key = ?", (key,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set_sync_value(self, key: str, value: str) -> None:
        """Set a sync state value (upsert)."""
        conn = self._require_conn()
        now = _ts_ms()
        await conn.execute(
            """INSERT INTO sync_state (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?""",
            (key, value, now, value, now),
        )
        await conn.commit()

    # --- Intelligence Layer: delta export ---

    async def get_sync_keys_by_prefix(self, prefix: str) -> list[dict[str, Any]]:
        """Get all sync_state entries whose key starts with prefix."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT key, value FROM sync_state WHERE key LIKE ?",
            (f"{prefix}%",),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_sync_key(self, key: str) -> None:
        """Delete a sync_state entry by key."""
        conn = self._require_conn()
        await conn.execute("DELETE FROM sync_state WHERE key = ?", (key,))
        await conn.commit()

    async def get_readings_since(self, since_ts_ms: int, limit: int = 50000) -> list[dict[str, Any]]:
        """Get sensor readings since a timestamp for delta export."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM sensor_readings WHERE ts > ? ORDER BY ts ASC LIMIT ?",
            (since_ts_ms, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_trips_since(self, since_ts_ms: int) -> list[dict[str, Any]]:
        """Get trips started since a timestamp."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM trips WHERE start_time > ? ORDER BY start_time ASC",
            (since_ts_ms,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def count_readings_since(self, since_ts_ms: int) -> int:
        """Count sensor readings since a timestamp."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM sensor_readings WHERE ts > ?", (since_ts_ms,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # --- Intelligence Layer: can_signals ---

    async def insert_can_signals(self, signals: list[tuple[int, str, float, str]]) -> None:
        """Batch insert decoded CAN signals.

        Args:
            signals: list of (timestamp_ms, signal_name, value, unit) tuples.
        """
        if not signals:
            return
        conn = self._require_conn()
        await conn.executemany(
            "INSERT INTO can_signals (ts, signal_name, value, unit) VALUES (?, ?, ?, ?)",
            signals,
        )
        await conn.commit()

    # --- Intelligence Layer: cold_starts ---

    async def insert_cold_start(
        self,
        trip_id: int | None,
        ambient_temp_c: float | None,
        start_coolant_c: float | None,
        target_coolant_c: float,
        warmup_seconds: float,
    ) -> None:
        """Record a cold-start warmup observation."""
        conn = self._require_conn()
        await conn.execute(
            """INSERT INTO cold_starts
               (trip_id, ambient_temp_c, start_coolant_c, target_coolant_c, warmup_seconds, ts)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (trip_id, ambient_temp_c, start_coolant_c, target_coolant_c, warmup_seconds, _ts_ms()),
        )
        await conn.commit()

    async def get_cold_starts(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get cold-start records for warmup model fitting."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """SELECT * FROM cold_starts
               WHERE ambient_temp_c IS NOT NULL AND warmup_seconds > 0
               ORDER BY ts DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # --- Intelligence Layer: maintenance_log ---

    async def insert_maintenance(
        self,
        item: str,
        odometer_miles: float,
        next_due_miles: float,
        notes: str = "",
    ) -> int:
        """Record a completed maintenance event."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """INSERT INTO maintenance_log (item, done_at, odometer_miles, next_due_miles, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (item, _ts_ms(), odometer_miles, next_due_miles, notes),
        )
        await conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("insert_maintenance returned no lastrowid")
        return cursor.lastrowid

    async def get_latest_maintenance(self, item: str) -> dict[str, Any] | None:
        """Get the most recent maintenance record for an item."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM maintenance_log WHERE item = ? ORDER BY done_at DESC LIMIT 1",
            (item,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_maintenance(self) -> list[dict[str, Any]]:
        """Get the latest maintenance record for each item."""
        conn = self._require_conn()
        cursor = await conn.execute(
            """SELECT m.* FROM maintenance_log m
               INNER JOIN (
                   SELECT item, MAX(done_at) as max_done
                   FROM maintenance_log GROUP BY item
               ) latest ON m.item = latest.item AND m.done_at = latest.max_done
               ORDER BY m.item""",
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def count_maintenance_by_item(self, item: str) -> int:
        """Count how many times a specific maintenance item has been done."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM maintenance_log WHERE item = ?", (item,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_cumulative_miles(self) -> float:
        """Get total miles from all completed trips."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT COALESCE(SUM(distance_miles), 0) FROM trips WHERE end_time IS NOT NULL",
        )
        row = await cursor.fetchone()
        return float(row[0]) if row else 0.0

    # --- purge (updated to include intelligence tables) ---

    async def purge_all(self) -> dict[str, int]:
        """Delete ALL data from all tables. Used by go-live to remove simulation data.

        Returns a dict of table name -> rows deleted.
        """
        conn = self._require_conn()
        tables = [
            "sensor_readings", "trips", "fillups", "health_scores", "can_frames",
            "alert_queue", "sync_state", "maintenance_log", "can_signals", "cold_starts",
        ]
        purged: dict[str, int] = {}
        for table in tables:
            cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            row = await cursor.fetchone()
            count = row[0] if row else 0
            await conn.execute(f"DELETE FROM {table}")  # noqa: S608
            purged[table] = count
        await conn.commit()
        # Reclaim disk space
        await conn.execute("VACUUM")
        logger.warning("purge_all: deleted %s", purged)
        return purged
