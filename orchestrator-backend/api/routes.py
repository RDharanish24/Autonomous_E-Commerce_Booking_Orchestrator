"""
api/routes.py

HTTP route definitions for the Autonomous E-Commerce & Booking Orchestrator.
Exposes:
  POST /orchestrate       — submit a new booking/search goal
  GET  /status/{task_id}  — poll current task state
  GET  /tasks             — list all tasks (paginated)
  DELETE /tasks/{task_id} — cancel a pending task
  WebSocket /ws/{task_id} — real-time task progress updates
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import JSONResponse

from core.exceptions import VendorError, AIParseError
from models.schemas import (
    OrchestrateRequest,
    OrchestrateResponse,
    TaskStatusResponse,
    TaskListResponse,
    ErrorResponse,
)
from services.dynamodb_service import DynamoDBService
from services.websocket_service import WebSocketManager
from tasks.worker import run_orchestration_pipeline

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared WebSocket manager — holds active connections keyed by task_id.
# Instantiated here so both the route handlers and the Celery worker callback
# can reference the same manager when running in-process (dev mode).
# In production the worker broadcasts via Redis pub/sub; see websocket_service.py.
ws_manager = WebSocketManager()

# DynamoDB service instance (stateless — safe to share across requests).
db = DynamoDBService()


# ---------------------------------------------------------------------------
# POST /orchestrate
# ---------------------------------------------------------------------------

@router.post(
    "/orchestrate",
    response_model=OrchestrateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new orchestration goal",
    responses={
        202: {"description": "Task accepted and queued"},
        422: {"description": "Validation error in request body"},
        500: {"description": "Internal server error"},
    },
)
async def orchestrate(payload: OrchestrateRequest) -> OrchestrateResponse:
    """
    Accept a user goal + constraints, persist a PENDING task record in
    DynamoDB, enqueue the Celery orchestration pipeline, and immediately
    return the task_id so the client can subscribe via WebSocket or poll
    /status/{task_id}.

    Flow:
        1. Validate incoming payload (handled by Pydantic).
        2. Create a PENDING record in DynamoDB → get task_id.
        3. Dispatch Celery task (non-blocking, .delay()).
        4. Return 202 with task_id + websocket_url.
    """
    try:
        # Step 1 — Persist initial PENDING state
        task_id = await db.create_task(
            goal=payload.goal,
            constraints=payload.constraints.model_dump(),
            category=payload.category,
        )
        logger.info("Task created: task_id=%s goal='%s'", task_id, payload.goal)

        # Step 2 — Enqueue background job (fire-and-forget)
        run_orchestration_pipeline.delay(
            task_id=task_id,
            goal=payload.goal,
            constraints=payload.constraints.model_dump(),
            category=payload.category,
        )
        logger.info("Celery job dispatched: task_id=%s", task_id)

        return OrchestrateResponse(
            task_id=task_id,
            status="PENDING",
            message="Task accepted. Connect to the websocket_url for live updates.",
            websocket_url=f"/ws/{task_id}",
        )

    except Exception as exc:
        logger.exception("Failed to create orchestration task: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue orchestration task. Please try again.",
        ) from exc


# ---------------------------------------------------------------------------
# GET /status/{task_id}
# ---------------------------------------------------------------------------

@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Poll task status",
    responses={
        200: {"description": "Task record returned"},
        404: {"description": "Task not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Return the current state of a task from DynamoDB.

    Possible status values:
        PENDING   — queued, not yet picked up by a worker
        RUNNING   — worker is actively fetching vendors / calling AI
        COMPLETED — AI decision made; result field is populated
        FAILED    — all vendors failed or AI returned un-parseable output
        CANCELLED — task was cancelled before a worker picked it up
    """
    try:
        record = await db.get_task(task_id)
    except Exception as exc:
        logger.exception("DynamoDB read error for task_id=%s: %s", task_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve task. Please try again.",
        ) from exc

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    return TaskStatusResponse(**record)


# ---------------------------------------------------------------------------
# GET /tasks  (paginated listing)
# ---------------------------------------------------------------------------

@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="List all orchestration tasks",
    responses={
        200: {"description": "Paginated list of tasks"},
        500: {"description": "Internal server error"},
    },
)
async def list_tasks(
    limit: int = Query(default=20, ge=1, le=100, description="Max items to return"),
    last_evaluated_key: Optional[str] = Query(
        default=None,
        description="Pagination cursor from the previous response (base64-encoded DynamoDB key)",
    ),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by task status (PENDING | RUNNING | COMPLETED | FAILED | CANCELLED)",
    ),
) -> TaskListResponse:
    """
    Return a paginated list of all tasks ordered by creation time (newest first).
    Pass `last_evaluated_key` from a previous response to fetch the next page.
    """
    try:
        tasks, next_key = await db.list_tasks(
            limit=limit,
            last_evaluated_key=last_evaluated_key,
            status_filter=status_filter,
        )
        return TaskListResponse(tasks=tasks, next_page_key=next_key)
    except Exception as exc:
        logger.exception("Failed to list tasks: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve task list.",
        ) from exc


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}  (cancel)
# ---------------------------------------------------------------------------

@router.delete(
    "/tasks/{task_id}",
    summary="Cancel a pending task",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Task cancelled"},
        404: {"description": "Task not found"},
        409: {"description": "Task already running or completed — cannot cancel"},
        500: {"description": "Internal server error"},
    },
)
async def cancel_task(task_id: str) -> JSONResponse:
    """
    Mark a PENDING task as CANCELLED in DynamoDB.
    Tasks in RUNNING / COMPLETED / FAILED state cannot be cancelled — the
    worker is either mid-flight or already done.
    """
    try:
        record = await db.get_task(task_id)
    except Exception as exc:
        logger.exception("DynamoDB read error on cancel: task_id=%s", task_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve task.",
        ) from exc

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )

    if record["status"] != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Task is in '{record['status']}' state and cannot be cancelled. "
                "Only PENDING tasks can be cancelled."
            ),
        )

    try:
        await db.update_task_status(task_id, "CANCELLED")
        logger.info("Task cancelled: task_id=%s", task_id)
        return JSONResponse(
            content={"task_id": task_id, "status": "CANCELLED", "message": "Task successfully cancelled."}
        )
    except Exception as exc:
        logger.exception("Failed to cancel task_id=%s: %s", task_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task.",
        ) from exc


# ---------------------------------------------------------------------------
# WebSocket  /ws/{task_id}
# ---------------------------------------------------------------------------

@router.websocket("/ws/{task_id}")
async def websocket_task_updates(websocket: WebSocket, task_id: str) -> None:
    """
    Real-time task progress channel.

    Protocol:
        1. Client connects → server sends the current snapshot from DynamoDB.
        2. As the Celery worker emits progress events (via Redis pub/sub),
           the server forwards them to this socket as JSON.
        3. On COMPLETED or FAILED the server sends the final record and
           closes the connection gracefully.

    Message envelope (server → client):
        {
          "event":   "snapshot" | "progress" | "completed" | "failed" | "cancelled",
          "task_id": "<uuid>",
          "data":    { ... task fields ... }
        }

    Client can send:
        { "action": "ping" }  → server replies { "event": "pong" }
    """
    await ws_manager.connect(websocket, task_id)
    logger.info("WebSocket connected: task_id=%s", task_id)

    try:
        # --- 1. Send current snapshot immediately on connect ---
        record = await db.get_task(task_id)
        if not record:
            await websocket.send_json({
                "event": "error",
                "task_id": task_id,
                "data": {"message": f"Task '{task_id}' not found."},
            })
            await websocket.close(code=4004)
            return

        await websocket.send_json({
            "event": "snapshot",
            "task_id": task_id,
            "data": record,
        })

        # If task is already terminal, close immediately — nothing more to stream.
        if record["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            await websocket.close(code=1000)
            return

        # --- 2. Subscribe to Redis pub/sub and forward events ---
        async for message in ws_manager.subscribe(task_id):
            # Forward the pub/sub message to the client
            await websocket.send_json(message)

            # Handle client keep-alive pings concurrently
            try:
                client_msg_raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.01
                )
                client_msg = json.loads(client_msg_raw)
                if client_msg.get("action") == "ping":
                    await websocket.send_json({"event": "pong", "task_id": task_id})
            except asyncio.TimeoutError:
                pass  # No client message — expected in most ticks
            except json.JSONDecodeError:
                pass  # Malformed client message — ignore

            # Close once the task reaches a terminal state
            if message.get("event") in ("completed", "failed", "cancelled"):
                logger.info(
                    "WebSocket closing — terminal event '%s': task_id=%s",
                    message["event"],
                    task_id,
                )
                await websocket.close(code=1000)
                return

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client: task_id=%s", task_id)
    except Exception as exc:
        logger.exception("WebSocket error: task_id=%s error=%s", task_id, exc)
        try:
            await websocket.send_json({
                "event": "error",
                "task_id": task_id,
                "data": {"message": "Internal server error. Connection closing."},
            })
            await websocket.close(code=1011)
        except Exception:
            pass  # Socket may already be dead
    finally:
        await ws_manager.disconnect(websocket, task_id)
        logger.info("WebSocket cleaned up: task_id=%s", task_id)