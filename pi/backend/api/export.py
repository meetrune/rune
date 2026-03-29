"""Rune Resilient Export -- chunked, SHA-verified database export.

Solves the problem of unreliable WiFi between Pi and iPhone: if a 500MB
DB download drops at 400MB, the old `/api/export` gave a corrupt file.

Architecture:
  1. POST /api/export/prepare -- backup DB, split into 5MB chunks, SHA-256 each
  2. GET /api/export/stream/{session_id} -- Pi reassembles chunks and streams
  3. GET /api/export/status/{session_id} -- check if session is still valid
  4. POST /api/export/complete/{session_id} -- cleanup temp files

The chunk layer is server-side integrity infrastructure. The iPhone downloads
the assembled stream in one GET. If WiFi drops, it re-hits the same URL and
gets the same bytes (idempotent, same backup, same chunks).

Sessions expire after 24 hours. Stale sessions are cleaned up in the
hourly maintenance loop.

References:
- SQLite backup API: https://www.sqlite.org/backup.html
- FastAPI StreamingResponse: used with async generator for low memory footprint
- SHA-256 per chunk: detects SD card bit rot before serving corrupt data
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import time
import uuid
from typing import Any, AsyncGenerator

from pydantic import BaseModel, Field

from backend.database.db import RuneDatabase

logger = logging.getLogger(__name__)

# Session key prefix in sync_state table
_SESSION_PREFIX = "export_session_"

# Default chunk size: 5MB -- small enough for reliable WiFi transfer,
# large enough to avoid excessive file I/O overhead on SD cards
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024

# Read buffer for SHA hashing and streaming (64KB keeps memory flat)
_READ_BUFFER = 65536

# Session TTL: 24 hours
SESSION_TTL_SECONDS = 86400


class ChunkMeta(BaseModel):
    """Metadata for one chunk of the export."""
    index: int
    size_bytes: int
    sha256: str


class ExportSession(BaseModel):
    """A prepared export session with chunk metadata."""
    session_id: str
    created_at: float
    expires_at: float
    total_bytes: int
    total_sha256: str
    chunk_count: int
    chunk_size_bytes: int
    chunks: list[ChunkMeta]
    export_dir: str  # Absolute path on Pi filesystem


def _get_export_base_dir(db_path: str) -> str:
    """Get the export directory adjacent to the DB file.

    Uses the DB's parent directory so exports land on the same filesystem
    as the DB (important if /tmp is a RAM overlay with limited space).
    """
    return os.path.join(os.path.dirname(db_path), "exports")


def _split_and_hash(
    backup_path: str,
    export_dir: str,
    chunk_size: int,
) -> tuple[list[ChunkMeta], str, int]:
    """Split a backup file into chunks and compute SHA-256 for each.

    Runs in a thread (called via asyncio.to_thread) because it's
    sequential file I/O that would block the event loop.

    Returns (chunks, total_sha256, total_bytes).
    """
    os.makedirs(export_dir, exist_ok=True)

    chunks: list[ChunkMeta] = []
    total_hasher = hashlib.sha256()
    total_bytes = 0
    chunk_index = 0

    with open(backup_path, "rb") as f:
        while True:
            # Read one chunk
            chunk_hasher = hashlib.sha256()
            chunk_path = os.path.join(export_dir, f"chunk_{chunk_index:04d}.bin")
            chunk_bytes = 0

            with open(chunk_path, "wb") as cf:
                bytes_remaining = chunk_size
                while bytes_remaining > 0:
                    buf = f.read(min(_READ_BUFFER, bytes_remaining))
                    if not buf:
                        break
                    cf.write(buf)
                    chunk_hasher.update(buf)
                    total_hasher.update(buf)
                    chunk_bytes += len(buf)
                    bytes_remaining -= len(buf)

            if chunk_bytes == 0:
                # End of file, remove empty chunk file
                os.remove(chunk_path)
                break

            chunks.append(ChunkMeta(
                index=chunk_index,
                size_bytes=chunk_bytes,
                sha256=chunk_hasher.hexdigest(),
            ))
            total_bytes += chunk_bytes
            chunk_index += 1

    # Remove the monolithic backup (chunks are the source of truth now)
    try:
        os.remove(backup_path)
    except OSError:
        pass

    return chunks, total_hasher.hexdigest(), total_bytes


async def prepare_export(
    db: RuneDatabase,
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE,
) -> ExportSession:
    """Create a backup, split into chunks, compute SHAs.

    This is the expensive call -- runs backup + split in thread pool.
    Returns an ExportSession with all chunk metadata.

    Raises RuntimeError if insufficient disk space.
    """
    db_path = db._db_path
    base_dir = _get_export_base_dir(db_path)
    session_id = uuid.uuid4().hex[:16]
    export_dir = os.path.join(base_dir, session_id)
    backup_path = os.path.join(export_dir, "backup.db")

    # Check available disk space
    os.makedirs(export_dir, exist_ok=True)
    disk = shutil.disk_usage(os.path.dirname(db_path))
    db_size = await db.get_db_size_bytes()
    # Need ~2x DB size: backup + chunks (backup is deleted after split)
    if disk.free < db_size * 2.2:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise RuntimeError(
            f"Insufficient disk space: {disk.free // 1_048_576}MB free, "
            f"need ~{(db_size * 2.2) // 1_048_576}MB for export"
        )

    # Create backup
    await db.backup(backup_path)

    # Split into chunks and compute SHAs (blocking I/O, run in thread)
    chunks, total_sha, total_bytes = await asyncio.to_thread(
        _split_and_hash, backup_path, export_dir, chunk_size_bytes,
    )

    now = time.time()
    session = ExportSession(
        session_id=session_id,
        created_at=now,
        expires_at=now + SESSION_TTL_SECONDS,
        total_bytes=total_bytes,
        total_sha256=total_sha,
        chunk_count=len(chunks),
        chunk_size_bytes=chunk_size_bytes,
        chunks=chunks,
        export_dir=export_dir,
    )

    # Persist session to sync_state table
    await db.set_sync_value(
        f"{_SESSION_PREFIX}{session_id}",
        session.model_dump_json(),
    )

    logger.info(
        "Export prepared: session=%s total=%dMB chunks=%d",
        session_id, total_bytes // 1_048_576, len(chunks),
    )
    return session


async def get_export_session(
    db: RuneDatabase,
    session_id: str,
) -> ExportSession | None:
    """Load an export session from the database. Returns None if expired or missing."""
    raw = await db.get_sync_value(f"{_SESSION_PREFIX}{session_id}")
    if raw is None:
        return None

    try:
        session = ExportSession.model_validate_json(raw)
    except Exception:
        logger.warning("Corrupt export session: %s", session_id)
        return None

    # Check expiry
    if time.time() > session.expires_at:
        logger.info("Export session expired: %s", session_id)
        await _cleanup_session(db, session)
        return None

    # Check chunk files still exist on disk
    if not os.path.isdir(session.export_dir):
        logger.warning("Export session dir missing: %s", session.export_dir)
        await _delete_session_key(db, session_id)
        return None

    return session


async def stream_export(
    session: ExportSession,
) -> AsyncGenerator[bytes, None]:
    """Async generator that streams chunk files in order.

    Validates each chunk's SHA-256 before yielding its bytes.
    Aborts with RuntimeError if a chunk is corrupt (SD card issue).

    Memory footprint: 64KB read buffer regardless of DB size.
    """
    for chunk in session.chunks:
        chunk_path = os.path.join(session.export_dir, f"chunk_{chunk.index:04d}.bin")

        if not os.path.exists(chunk_path):
            raise RuntimeError(
                f"Chunk file missing: {chunk_path} -- session may need to be re-prepared"
            )

        # Verify SHA before streaming (catches SD card bit rot)
        hasher = hashlib.sha256()
        with open(chunk_path, "rb") as f:
            while True:
                buf = f.read(_READ_BUFFER)
                if not buf:
                    break
                hasher.update(buf)

        if hasher.hexdigest() != chunk.sha256:
            raise RuntimeError(
                f"Chunk {chunk.index} SHA mismatch: expected {chunk.sha256}, "
                f"got {hasher.hexdigest()} -- possible SD card corruption"
            )

        # Stream the verified chunk
        with open(chunk_path, "rb") as f:
            while True:
                buf = f.read(_READ_BUFFER)
                if not buf:
                    break
                yield buf


async def complete_export(
    db: RuneDatabase,
    session_id: str,
) -> dict[str, Any]:
    """Clean up chunk files and session state after successful download."""
    session = await get_export_session(db, session_id)
    if session is None:
        return {"ok": False, "error": "session not found or expired"}

    await _cleanup_session(db, session)
    logger.info("Export completed and cleaned up: session=%s", session_id)
    return {"ok": True, "bytes_served": session.total_bytes}


async def cleanup_stale_sessions(
    db: RuneDatabase,
    max_age_seconds: int = SESSION_TTL_SECONDS,
) -> int:
    """Delete export sessions older than max_age_seconds.

    Called from the hourly maintenance loop. Removes both chunk files
    and sync_state keys for expired sessions.
    """
    rows = await db.get_sync_keys_by_prefix(_SESSION_PREFIX)

    deleted = 0
    now = time.time()
    for row in rows:
        try:
            session = ExportSession.model_validate_json(row["value"])
            if now > session.expires_at:
                await _cleanup_session(db, session)
                deleted += 1
        except Exception:
            # Corrupt session -- clean up the key
            await _delete_session_key(db, row["key"].replace(_SESSION_PREFIX, ""))
            deleted += 1

    return deleted


async def _cleanup_session(db: RuneDatabase, session: ExportSession) -> None:
    """Remove chunk files from disk and session key from DB."""
    if os.path.isdir(session.export_dir):
        await asyncio.to_thread(shutil.rmtree, session.export_dir, True)
    await _delete_session_key(db, session.session_id)


async def _delete_session_key(db: RuneDatabase, session_id: str) -> None:
    """Remove session key from sync_state table."""
    await db.delete_sync_key(f"{_SESSION_PREFIX}{session_id}")
