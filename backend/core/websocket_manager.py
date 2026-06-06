import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Dictionary to store active WebSocket connections mapped by client_id
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accepts a new WebSocket connection and stores it."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"[WS] Client {client_id} connected. Total active: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        """Removes a disconnected WebSocket from the active list."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"[WS] Client {client_id} disconnected. Total active: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, client_id: str):
        """Sends a JSON message to a specific connected client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"[WS ERROR] Failed to send message to {client_id}: {e}")
                self.disconnect(client_id)

# Global singleton instance to be imported across the application
manager = ConnectionManager()
