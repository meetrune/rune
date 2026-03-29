"""Raw CAN bus frame listener for WiCAN Pro.

Connects to WiCAN Pro's raw CAN TCP port (35000) alongside the ELM327
OBD-II connection (3333). Captures every CAN frame on the powertrain
F-CAN bus and stores them in SQLite for offline analysis on the Mac.

WiCAN Pro raw CAN format (JSON over TCP, newline-delimited):
  {"bus":"0","type":"rx","ts":12345,"frame":[{"id":464,"dlc":8,"data":[0,0,15,160,0,0,0,0]}]}

CAN IDs are decimal. Data bytes are integers 0-255.

This gives us access to signals the ELM327 mode can't see:
  0x1D0 (464) -- Individual wheel speeds (all 4 corners)
  0x14A (330) -- Steering angle sensor
  0x17C (380) -- Steering torque (EPS motor output)
  0x320 (800) -- VTEC activation state
  0x324 (804) -- TRIP_FUEL_CONSUMED counter + coolant
  0x405 (1029) -- Door status

Safety: This is a PASSIVE listener. It opens a TCP socket and reads.
It never writes to the CAN bus. Read-only by design.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# How many frames to buffer before flushing to DB
_FLUSH_INTERVAL_SECONDS = 1.0
_MAX_BUFFER_SIZE = 500


@dataclass(frozen=True)
class CANFrame:
    """A single raw CAN frame from the bus."""
    timestamp_ms: int  # Unix milliseconds (when we received it)
    can_id: int        # CAN arbitration ID (decimal)
    dlc: int           # Data length code (0-8)
    data: bytes        # Raw data bytes
    bus: int = 0       # Bus number (0 for F-CAN powertrain)


@dataclass
class CANListenerStats:
    """Runtime statistics for the CAN listener."""
    frames_received: int = 0
    frames_stored: int = 0
    frames_dropped: int = 0
    parse_errors: int = 0
    reconnect_count: int = 0
    last_frame_time: float = 0.0


class CANListener:
    """Async raw CAN frame listener for WiCAN Pro port 35000.

    Connects via TCP, reads JSON-formatted CAN frames, buffers them,
    and periodically flushes to the database. Runs as a background task
    alongside the OBD ELM327 polling on port 3333.
    """

    def __init__(
        self,
        host: str = "192.168.4.100",
        port: int = 35000,
        reconnect_delay: float = 5.0,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        self._host = host
        self._port = port
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

        self._buffer: list[CANFrame] = []
        self._buffer_lock = asyncio.Lock()
        self._db: object | None = None  # Set via start()

        self.stats = CANListenerStats()

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, db: object) -> None:
        """Start the CAN listener background task.

        Args:
            db: RuneDatabase instance (typed as object to avoid circular import).
        """
        self._db = db
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("CAN listener started: %s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the listener and flush remaining buffer."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Flush any remaining frames
        await self._flush_buffer()
        await self._disconnect()
        logger.info(
            "CAN listener stopped: %d frames received, %d stored, %d dropped",
            self.stats.frames_received, self.stats.frames_stored, self.stats.frames_dropped,
        )

    async def _connect(self) -> bool:
        """Open TCP connection to WiCAN Pro raw CAN port."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=10.0,
            )
            logger.info("CAN listener connected to %s:%d", self._host, self._port)
            return True
        except (OSError, asyncio.TimeoutError) as e:
            logger.warning("CAN listener connect failed: %s", e)
            return False

    async def _disconnect(self) -> None:
        """Close TCP connection."""
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    def _parse_frame(self, line: bytes) -> list[CANFrame]:
        """Parse a JSON line from WiCAN Pro into CANFrame(s).

        WiCAN format: {"bus":"0","type":"rx","frame":[{"id":464,"dlc":8,"data":[0,0,15,160,...]}]}
        Can contain multiple frames per message.
        """
        frames: list[CANFrame] = []
        try:
            msg = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.stats.parse_errors += 1
            return frames

        if msg.get("type") != "rx":
            return frames

        bus = int(msg.get("bus", 0))
        ts_ms = int(time.time() * 1000)

        for f in msg.get("frame", []):
            try:
                can_id = int(f["id"])
                dlc = int(f.get("dlc", len(f.get("data", []))))
                data_ints = f.get("data", [])
                data_bytes = bytes(data_ints[:8])  # Cap at 8 bytes for CAN 2.0
                frames.append(CANFrame(
                    timestamp_ms=ts_ms,
                    can_id=can_id,
                    dlc=dlc,
                    data=data_bytes,
                    bus=bus,
                ))
            except (KeyError, ValueError, TypeError):
                self.stats.parse_errors += 1

        return frames

    async def _flush_buffer(self) -> None:
        """Write buffered frames to the database."""
        async with self._buffer_lock:
            if not self._buffer:
                return
            frames_to_write = self._buffer.copy()
            self._buffer.clear()

        if self._db is None:
            self.stats.frames_dropped += len(frames_to_write)
            return

        try:
            # Call insert_can_frames on the database
            await self._db.insert_can_frames(frames_to_write)  # type: ignore[attr-defined]
            self.stats.frames_stored += len(frames_to_write)
        except Exception:
            logger.exception("Failed to write %d CAN frames to DB", len(frames_to_write))
            self.stats.frames_dropped += len(frames_to_write)

    async def _listen_loop(self) -> None:
        """Main loop: connect, read frames, buffer, flush periodically."""
        backoff = self._reconnect_delay

        while self._running:
            try:
                # Connect
                if not await self._connect():
                    self.stats.reconnect_count += 1
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, self._max_reconnect_delay)
                    continue

                # Reset backoff on successful connect
                backoff = self._reconnect_delay
                last_flush = time.monotonic()

                # Read loop
                while self._running and self._reader is not None:
                    try:
                        line = await asyncio.wait_for(
                            self._reader.readline(),
                            timeout=30.0,  # WiCAN sends frequently; 30s = stale
                        )
                    except asyncio.TimeoutError:
                        logger.warning("CAN listener: no data for 30s, reconnecting")
                        break

                    if not line:
                        logger.warning("CAN listener: connection closed by WiCAN")
                        break

                    frames = self._parse_frame(line)
                    if frames:
                        self.stats.frames_received += len(frames)
                        self.stats.last_frame_time = time.time()

                        async with self._buffer_lock:
                            self._buffer.extend(frames)

                            # Safety cap
                            if len(self._buffer) > _MAX_BUFFER_SIZE:
                                overflow = len(self._buffer) - _MAX_BUFFER_SIZE
                                self._buffer = self._buffer[overflow:]
                                self.stats.frames_dropped += overflow

                    # Flush every second
                    now = time.monotonic()
                    if now - last_flush >= _FLUSH_INTERVAL_SECONDS:
                        await self._flush_buffer()
                        last_flush = now

                # Disconnected -- flush and retry
                await self._flush_buffer()
                await self._disconnect()
                self.stats.reconnect_count += 1

            except asyncio.CancelledError:
                await self._flush_buffer()
                return
            except Exception:
                logger.exception("CAN listener error")
                await self._disconnect()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._max_reconnect_delay)

    def get_debug_state(self) -> dict[str, object]:
        """Return listener stats for diagnostics."""
        return {
            "running": self._running,
            "connected": self._writer is not None,
            "host": self._host,
            "port": self._port,
            "frames_received": self.stats.frames_received,
            "frames_stored": self.stats.frames_stored,
            "frames_dropped": self.stats.frames_dropped,
            "parse_errors": self.stats.parse_errors,
            "reconnect_count": self.stats.reconnect_count,
            "last_frame_time": self.stats.last_frame_time,
            "buffer_size": len(self._buffer),
        }
