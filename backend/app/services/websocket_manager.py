"""
WebSocket Connection Manager for CITYVISION AI Live Telemetry & Alerts
Problem Statement ID: SIH26127
"""
import logging
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("cityvision.websocket")


class ConnectionManager:
    """Manages connected WebSocket clients for real-time dashboard telemetry."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.loop: Any = None

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts and registers a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            import asyncio
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        logger.info(f"WebSocket client connected. Total active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a disconnected WebSocket client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """Sends a JSON message to an individual WebSocket client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message to client: {e}")

    async def broadcast_json(self, data: Dict[str, Any]) -> None:
        """Broadcasts a JSON event payload to all currently connected dashboard clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"Error broadcasting to client, queuing for disconnect: {e}")
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)

    def dispatch_broadcast(self, data: Dict[str, Any]) -> None:
        """Thread-safe dispatcher to broadcast messages across active connections."""
        if not self.active_connections:
            return

        import asyncio
        try:
            curr_loop = None
            try:
                curr_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if curr_loop and curr_loop.is_running():
                asyncio.create_task(self.broadcast_json(data))
            elif self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_json(data), self.loop)
        except Exception as e:
            logger.debug(f"Telemetry broadcast dispatch failure: {e}")


# Global singleton instance
ws_manager = ConnectionManager()
