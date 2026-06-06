from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from models.schemas import OrchestratorRequest, TaskStatus, FallbackDecision
from models.dynamodb import TaskRecord
import uuid
import json
import logging
from services.dynamodb_service import create_task_record, get_task_record, complete_task_with_decision
from services.fetcher import fetch_flights_concurrently
from services.ai_evaluator import evaluate_flights

logger = logging.getLogger(__name__)
router = APIRouter()


from core.websocket_manager import manager

async def push_status(client_id: str, status: str, payload: dict = None):
    """Utility to safely broadcast a status update to a connected client."""
    if client_id:
        await manager.send_personal_message({
            "status": status,
            "payload": payload or {}
        }, client_id)

async def run_orchestration_pipeline(task_id: str, constraints: dict, client_id: str = None):
    """
    Full orchestration pipeline (Phases 2 + 3):
      Phase 2 → Concurrent vendor fetching & aggregation
      Phase 3 → Gemini AI evaluation → DynamoDB completion update
    """
    logger.info("[PIPELINE] Starting orchestration for task_id: %s", task_id)
    await push_status(client_id, "Task Queued", {"task_id": task_id})

    # ─────────────────────────────────────────────────────────────
    # PHASE 2: Concurrent Flight Fetching
    # ─────────────────────────────────────────────────────────────
    try:
        await push_status(client_id, "Fetching Vendor APIs", {"constraints": constraints})
        results = await fetch_flights_concurrently(constraints)
        logger.info("[PIPELINE] Phase 2 complete. Aggregated %d flight options.", len(results))

        print("\n" + "=" * 85, flush=True)
        print(f"  PHASE 2 — AGGREGATED FLIGHT DATA FOR TASK {task_id}:", flush=True)
        print("=" * 85, flush=True)
        print(json.dumps(results, indent=2), flush=True)
        print("=" * 85 + "\n", flush=True)

    except Exception as exc:
        logger.exception("[PIPELINE ERROR] Phase 2 fetching failed for task_id %s: %s", task_id, exc)
        fallback = FallbackDecision(
            reasoning=f"Phase 2 vendor fetching failed completely.",
            error_detail=str(exc),
        )
        complete_task_with_decision(task_id, fallback.model_dump(mode="json"), is_fallback=True)
        await push_status(client_id, "Human Review Required", {"error": str(exc), "phase": 2})
        return

    if not results:
        logger.warning("[PIPELINE] No flight options returned. Skipping AI evaluation.")
        fallback = FallbackDecision(
            reasoning="All vendors returned zero results. No flights to evaluate.",
            error_detail="Empty aggregated results from Phase 2.",
        )
        complete_task_with_decision(task_id, fallback.model_dump(mode="json"), is_fallback=True)
        await push_status(client_id, "Human Review Required", {"error": "Zero flights found", "phase": 2})
        return

    # ─────────────────────────────────────────────────────────────
    # PHASE 3: AI Evaluation via Gemini
    # ─────────────────────────────────────────────────────────────
    constraints_str = ", ".join(f"{k}: {v}" for k, v in constraints.items()) if constraints else "No specific constraints"

    logger.info("[PIPELINE] Phase 3 — Sending %d flights to Gemini AI evaluator...", len(results))
    await push_status(client_id, "Evaluating Constraints", {"flights_found": len(results)})
    decision = evaluate_flights(constraints=constraints_str, flights=results)

    # ── Print AI Decision to Terminal ──
    is_fallback = isinstance(decision, FallbackDecision)
    decision_dict = decision.model_dump(mode="json")

    print("\n" + "=" * 85, flush=True)
    if is_fallback:
        print(f"  PHASE 3 — ⚠ FALLBACK DECISION (Human Review Required)", flush=True)
        await push_status(client_id, "Human Review Required", {"error": decision_dict.get("error_detail"), "phase": 3})
    else:
        print(f"  PHASE 3 — ✓ AI EVALUATION DECISION", flush=True)
        await push_status(client_id, "Optimal Decision Reached", {"decision": decision_dict})
        
    print("=" * 85, flush=True)
    print(json.dumps(decision_dict, indent=2), flush=True)
    print("=" * 85 + "\n", flush=True)

    # ── Persist to DynamoDB ──
    db_success = complete_task_with_decision(task_id, decision_dict, is_fallback=is_fallback)
    if db_success:
        logger.info("[PIPELINE] ✓ Task %s persisted to DynamoDB as %s.",
                     task_id, "FAILED" if is_fallback else "COMPLETED")
    else:
        logger.error("[PIPELINE] ✗ DynamoDB update failed for task %s. Decision was printed above.", task_id)


@router.post("/orchestrate", status_code=status.HTTP_202_ACCEPTED)
async def start_orchestration(request: OrchestratorRequest, background_tasks: BackgroundTasks):
    # 1. Generate a unique ID for this job
    task_id = str(uuid.uuid4())
    
    # 2. Add the full orchestration pipeline (Phase 2 + 3) to BackgroundTasks
    background_tasks.add_task(run_orchestration_pipeline, task_id, request.constraints, request.client_id)
    
    # 3. Immediately return 202 Accepted with task_id
    return {
        "task_id": task_id,
        "status": "ACCEPTED",
        "message": "Task accepted. Running flight fetch + AI evaluation in the background."
    }

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    # Fetch the current state from DynamoDB with a graceful fallback
    try:
        record = get_task_record(task_id)
        if record:
            return record
    except Exception as e:
        logger.warning("Could not fetch from DynamoDB: %s. Returning mock status.", e)
        
    return {
        "task_id": task_id,
        "status": "COMPLETED_OR_UNKNOWN",
        "message": "DynamoDB is unreachable. Please verify background job logs in the terminal console."
    }