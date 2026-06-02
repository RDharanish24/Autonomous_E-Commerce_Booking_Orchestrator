"""
api/websockets.py

WebSocket endpoint for real-time orchestration task progress updates.

Responsibilities:
  - Accept and manage WebSocket connections keyed by task_id
  - Send an immediate state snapshot from DynamoDB on connect
  - Forward live progress events from Redis pub/sub to the client
  - Handle client keep-alive pings
  - Gracefully close on terminal task states or client disconnect

Message Envelope (server → client):
    {
      "event"  : "snapshot" | "progress" | "completed" | "failed" | "cancelled" | "error" | "pong",
      "task_id": "<uuid>",
      "data"   : { ...task fields or error detail... }
    }

Client → server (optional):
    { "action": "ping" }
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.config import settings
from services.dynamodb_service import DynamoDBService

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Redis pub/sub helpers
# ---------------------------------------------------------------------------

def _channel(task_id: str) -> str:
    """Canonical Redis channel name for a given task."""
    return f"task_updates:{task_id}"


async def _get_redis() -> aioredis.Redis:
    """Create a fresh async Redis connection for a single WebSocket session."""
    return await aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


# ---------------------------------------------------------------------------
# Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """
    Tracks active WebSocket connections in memory.

    In a single-process dev setup this is sufficient.
    In a multi-worker production deployment, the pub/sub subscription
    (Redis) is what guarantees delivery — this manager is only needed
    for connection bookkeeping within one process.
    """

    def __init__(self) -> None:
        # task_id → set of active WebSocket objects
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(task_id, set()).add(websocket)
        logger.debug(
            "WS connected | task_id=%s | total_connections=%d",
            task_id,
            len(self._connections[task_id]),
        )

    async def disconnect(self, websocket: WebSocket, task_id: str) -> None:
        bucket = self._connections.get(task_id, set())
        bucket.discard(websocket)
        if not bucket:
            self._connections.pop(task_id, None)
        logger.debug("WS disconnected | task_id=%s", task_id)

    def connection_count(self, task_id: str) -> int:
        return len(self._connections.get(task_id, set()))


manager = ConnectionManager()
db = DynamoDBService()

# ---------------------------------------------------------------------------
# Terminal state guard
# ---------------------------------------------------------------------------

TERMINAL_STATES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
TERMINAL_EVENTS = frozenset({"completed", "failed", "cancelled"})


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/{task_id}")
async def websocket_task_updates(websocket: WebSocket, task_id: str) -> None:
    """
    Real-time task progress channel.

    Lifecycle:
        1. Accept connection and register with ConnectionManager.
        2. Fetch current DynamoDB snapshot and send immediately.
        3. If task is already terminal → send final state and close.
        4. Otherwise subscribe to Redis channel and stream events.
        5. On terminal event or client disconnect → clean up and exit.
    """
    await manager.connect(websocket, task_id)
    redis: aioredis.Redis | None = None

    try:
        # ----------------------------------------------------------------
        # Step 1 — Immediate snapshot
        # ----------------------------------------------------------------
        record = await db.get_task(task_id)

        if not record:
            await _send(websocket, {
                "event": "error",
                "task_id": task_id,
                "data": {"message": f"Task '{task_id}' not found."},
            })
            await websocket.close(code=4004)
            return

        await _send(websocket, {
            "event": "snapshot",
            "task_id": task_id,
            "data": record,
        })

        # ----------------------------------------------------------------
        # Step 2 — Early exit if already terminal
        # ----------------------------------------------------------------
        if record.get("status") in TERMINAL_STATES:
            logger.info(
                "WS early-close — task already terminal | task_id=%s status=%s",
                task_id,
                record["status"],
            )
            await websocket.close(code=1000)
            return

        # ----------------------------------------------------------------
        # Step 3 — Subscribe to Redis pub/sub and stream events
        # ----------------------------------------------------------------
        redis = await _get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(_channel(task_id))
        logger.info("WS subscribed to Redis channel | task_id=%s", task_id)

        async for message in _iter_pubsub(pubsub, websocket, task_id):
            # Forward event to client
            await _send(websocket, message)

            # Close on terminal event
            if message.get("event") in TERMINAL_EVENTS:
                logger.info(
                    "WS closing on terminal event '%s' | task_id=%s",
                    message["event"],
                    task_id,
                )
                await websocket.close(code=1000)
                return

    except WebSocketDisconnect:
        logger.info("WS client disconnected | task_id=%s", task_id)

    except Exception as exc:
        logger.exception("WS unexpected error | task_id=%s | error=%s", task_id, exc)
        await _safe_send_error(websocket, task_id, "Internal server error.")
        await _safe_close(websocket, code=1011)

    finally:
        # Always clean up Redis and manager regardless of exit path
        if redis:
            try:
                await redis.aclose()
            except Exception:
                pass
        await manager.disconnect(websocket, task_id)
        logger.info("WS cleanup complete | task_id=%s", task_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _iter_pubsub(
    pubsub: aioredis.client.PubSub,
    websocket: WebSocket,
    task_id: str,
):
    """
    Async generator that yields parsed event dicts from the Redis pub/sub
    channel while concurrently handling client-sent ping messages.

    Yields one dict per valid published message.
    Exits cleanly when the client disconnects mid-stream.
    """
    POLL_INTERVAL = 0.05  # seconds — how often to check for new pub/sub messages

    while True:
        # --- Poll Redis ---
        raw = await pubsub.get_message(ignore_subscribe_messages=True, timeout=POLL_INTERVAL)

        if raw and raw.get("type") == "message":
            try:
                payload = json.loads(raw["data"])
                yield payload
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning(
                    "WS malformed pub/sub message | task_id=%s | error=%s | raw=%s",
                    task_id, exc, raw,
                )

        # --- Non-blocking client message check (ping/pong) ---
        try:
            client_raw = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=0.01,
            )
            client_msg = json.loads(client_raw)
            if client_msg.get("action") == "ping":
                await _send(websocket, {"event": "pong", "task_id": task_id, "data": {}})
        except asyncio.TimeoutError:
            pass  # Normal — no client message in this tick
        except json.JSONDecodeError:
            logger.debug("WS non-JSON client message ignored | task_id=%s", task_id)
        except WebSocketDisconnect:
            logger.info("WS client disconnected mid-stream | task_id=%s", task_id)
            return  # Stop the generator — triggers finally cleanup above


async def _send(websocket: WebSocket, payload: dict) -> None:
    """Send a JSON payload to the client. Logs and swallows send failures."""
    try:
        await websocket.send_json(payload)
    except Exception as exc:
        logger.warning("WS send failed | payload_event=%s | error=%s", payload.get("event"), exc)


async def _safe_send_error(websocket: WebSocket, task_id: str, message: str) -> None:
    """Best-effort error frame — used in exception handlers."""
    await _send(websocket, {
        "event": "error",
        "task_id": task_id,
        "data": {"message": message},
    })


async def _safe_close(websocket: WebSocket, code: int = 1000) -> None:
    """Best-effort close — socket may already be gone."""
    try:
        await websocket.close(code=code)
    except Exception:
        pass