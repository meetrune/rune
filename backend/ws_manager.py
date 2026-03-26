"""WebSocket connection manager.

Tracks connected clients and broadcasts messages to all of them.
Dead connections are detected on send failure and removed.

Pattern: single producer (OBD loop), multiple consumers (phone, debug clients).
"""

from __future__ import annotations

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


MAX_CONNECTIONS = 8  # Pi has limited resources: phone + diagnostics + dev browser


class ConnectionManager:
    """Manages WebSocket client connections for broadcasting."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new client. Rejects if at capacity."""
        if self.client_count >= MAX_CONNECTIONS:
            await websocket.close(code=1013, reason="Too many connections")
            logger.warning("Rejected WebSocket: %d/%d connections", self.client_count, MAX_CONNECTIONS)
            return
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("Client connected (%d total)", self.client_count)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a client. Safe to call multiple times (uses discard)."""
        self._connections.discard(websocket)
        logger.info("Client disconnected (%d remaining)", self.client_count)

    async def broadcast(self, message: str) -> None:
        """Send a pre-serialized message to all connected clients.

        Dead connections are caught and removed silently.
        Message should be JSON string -- serialize ONCE, send to all.
        """
        dead: set[WebSocket] = set()
        # Snapshot to avoid RuntimeError if another coroutine modifies the set
        # during iteration (e.g., concurrent broadcast + trip_ended event)
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        if dead:
            self._connections -= dead
            logger.warning("Removed %d dead connection(s)", len(dead))
