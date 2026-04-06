"""
WebSocket handler for real-time progress updates.

Provides broadcast functionality to all connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from ..scraper.models import DownloadProgress, WebSocketMessage, MediaItem
from ..utils.queue import queue_manager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for progress broadcasting."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and sync current state."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
            logger.info(f"WebSocket connected. Total connections: {len(self._connections)}")
        
        # 1. Sync current persistent queue to the new client
        pending = queue_manager.get_all()
        for album_name, items in pending.items():
            # Send album info
            await self.send_to_client(websocket, WebSocketMessage(
                type="album_info",
                data={"name": album_name, "count": len(items)}
            ))
            # Send media items to populate grid
            await self.send_to_client(websocket, WebSocketMessage(
                type="media_added",
                data={"items": [item.model_dump() for item in items]}
            ))
            
        # 2. Sync real-time progress for active items
        from ..api.routes import get_download_manager
        mgr = get_download_manager()
        for filename, progress in mgr._last_progress.items():
            await self.send_to_client(websocket, WebSocketMessage(
                type="progress",
                data=progress.model_dump()
            ))

    async def send_to_client(self, websocket: WebSocket, message: WebSocketMessage) -> None:
        """Send a message to a specific client."""
        try:
            data = message.model_dump()
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to send to client: {e}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self._connections)}")

    async def broadcast(self, message: WebSocketMessage) -> None:
        """
        Broadcast a message to all connected clients.

        Args:
            message: WebSocketMessage to broadcast
        """
        if not self._connections:
            return

        data = message.model_dump()
        json_data = json.dumps(data)

        async with self._lock:
            disconnected = []
            for connection in self._connections:
                try:
                    await connection.send_text(json_data)
                except Exception:
                    disconnected.append(connection)

            # Clean up disconnected clients
            for conn in disconnected:
                if conn in self._connections:
                    self._connections.remove(conn)

    async def broadcast_progress(self, progress: DownloadProgress) -> None:
        """Broadcast a download progress update."""
        await self.broadcast(WebSocketMessage(
            type="progress",
            data=progress.model_dump(),
        ))

    async def broadcast_album_info(self, name: str, count: int) -> None:
        """Broadcast album information."""
        await self.broadcast(WebSocketMessage(
            type="album_info",
            data={"name": name, "count": count},
        ))

    async def broadcast_file_start(self, filename: str, grid_uid: int | None = None) -> None:
        """Broadcast file download start."""
        data = {"filename": filename}
        if grid_uid is not None:
            data["gridUid"] = grid_uid
        await self.broadcast(WebSocketMessage(type="file_start", data=data))

    async def broadcast_media_added(self, items: list[MediaItem]) -> None:
        """Broadcast newly discovered (or resumed) media items."""
        await self.broadcast(WebSocketMessage(
            type="media_added",
            data={"items": [item.model_dump() for item in items]}
        ))

    async def broadcast_file_complete(
        self,
        filename: str,
        grid_uid: int | None = None,
        error: str | None = None
    ) -> None:
        """Broadcast file download completion."""
        data = {"filename": filename}
        if grid_uid is not None:
            data["gridUid"] = grid_uid
        if error:
            data["error"] = error
        await self.broadcast(WebSocketMessage(
            type="file_complete",
            data=data,
        ))

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self._connections)


# Global connection manager
ws_manager = ConnectionManager()


async def websocket_handler(websocket: WebSocket) -> None:
    """
    Handle a WebSocket connection.

    Keeps the connection alive and handles incoming messages.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Wait for any message (ping/pong or commands)
            data = await websocket.receive_text()
            # Handle potential commands from client
            try:
                message = json.loads(data)
                if message.get("type") == "cancel":
                    filename = message.get("data", {}).get("filename")
                    if filename:
                        from ..api.routes import get_download_manager
                        await get_download_manager().cancel(filename)
                        logger.info(f"Cancel request processed for: {filename}")
                
                # Could add command handling here (e.g., ping/pong)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await ws_manager.disconnect(websocket)