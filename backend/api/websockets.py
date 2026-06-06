from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time frontend updates.
    """
    await manager.connect(websocket, client_id)
    try:
        while True:
            # Keep the connection open and listen for any incoming keep-alive messages
            # In our current architecture, the frontend only receives data,
            # but we still need to wait on receive_text to catch disconnects cleanly.
            data = await websocket.receive_text()
            logger.debug(f"[WS] Received from {client_id}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(client_id)
