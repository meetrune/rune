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

import logging
import time
from typing import Any

import aiosqlite

from backend.obd_manager.models import HealthSnapshot, VehicleSnapshot

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id          INTEGER PRIMARY KEY,
    ts          INTEGER NOT NULL,
    rpm         REAL NOT NULL,
    speed_kph   REAL NOT NULL,
    coolant_c   REAL NOT NULL,
    engine_load REAL NOT NULL,
    maf_gps     REAL NOT NULL,
    stft_pct    REAL NOT NULL,
    ltft_pct    REAL NOT NULL,
    fuel_lvl    REAL NOT NULL,
    catalyst_c  REAL NOT NULL,
    oil_c       REAL NOT NULL,
    battery_v   REAL NOT NULL
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
    eco_score       REAL
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
                stft_pct, ltft_pct, fuel_lvl, catalyst_c, oil_c, battery_v)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(snap.timestamp * 1000), snap.rpm, snap.speed_kph,
                snap.coolant_temp_c, snap.engine_load_pct, snap.maf_gps,
                snap.stft_pct, snap.ltft_pct, snap.fuel_level_pct,
                snap.catalyst_temp_c, snap.oil_temp_c, snap.battery_voltage,
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
            )
            for s in snaps
        ]
        await conn.executemany(
            """INSERT INTO sensor_readings
               (ts, rpm, speed_kph, coolant_c, engine_load, maf_gps,
                stft_pct, ltft_pct, fuel_lvl, catalyst_c, oil_c, battery_v)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    async def end_trip(
        self,
        trip_id: int,
        end_time_ms: int,
        distance_miles: float,
        fuel_gallons: float,
        fuel_cost_usd: float,
        avg_mpg: float | None,
    ) -> None:
        """Finalize a trip with end time and totals."""
        conn = self._require_conn()
        await conn.execute(
            """UPDATE trips SET end_time=?, distance_miles=?, fuel_gallons=?,
               fuel_cost_usd=?, avg_mpg=? WHERE trip_id=?""",
            (end_time_ms, distance_miles, fuel_gallons, fuel_cost_usd, avg_mpg, trip_id),
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
