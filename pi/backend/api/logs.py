"""In-memory log ring buffer for the Rune diagnostics dashboard.

Stores the last N log records in a deque. Queryable by log level.
Thread-safe: emit() is protected by Handler.handle()'s RLock,
get_records() explicitly acquires the same lock.

No log records are stored as LogRecord objects -- we immediately
copy to a plain dict to avoid holding references to call frames.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any


class RuneLogBuffer(logging.Handler):
    """Logging handler that stores recent log records in a ring buffer.

    Attach to the root logger at startup. Query via get_records() from
    the /api/logs endpoint.
    """

    def __init__(self, capacity: int = 500, level: int = logging.DEBUG) -> None:
        super().__init__(level)
        self._buffer: deque[dict[str, Any]] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        """Store a log record. Called inside Handler.handle()'s lock."""
        try:
            entry: dict[str, Any] = {
                "timestamp": datetime.fromtimestamp(
                    record.created, tz=timezone.utc,
                ).isoformat(),
                "level": record.levelname,
                "levelno": record.levelno,
                "logger": record.name,
                "message": self.format(record),
            }
            self._buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_records(
        self,
        min_level: str = "DEBUG",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return records with level >= min_level, newest first.

        Acquires the handler's lock to prevent mid-iteration modification.
        """
        level_num = getattr(logging, min_level.upper(), logging.DEBUG)
        self.acquire()
        try:
            filtered = [
                e for e in self._buffer if e["levelno"] >= level_num
            ]
        finally:
            self.release()

        # Return newest first, limited
        return list(reversed(filtered[-limit:]))

    @property
    def count(self) -> int:
        """Number of records currently in the buffer."""
        return len(self._buffer)

    def clear(self) -> None:
        """Clear all records."""
        self.acquire()
        try:
            self._buffer.clear()
        finally:
            self.release()


# Singleton instance -- created at import, installed in main.py lifespan
log_buffer = RuneLogBuffer(capacity=500)
