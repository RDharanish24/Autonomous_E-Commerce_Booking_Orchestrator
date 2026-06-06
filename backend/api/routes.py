from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from models.schemas import OrchestratorRequest, TaskStatus
from models.dynamodb import TaskRecord
import uuid
import json
import logging
from services.dynamodb_service import create_task_record, get_task_record
from services.fetcher import fetch_flights_concurrently

logger = logging.getLogger(__name__)
router = APIRouter()

async def run_fetcher_background(task_id: str, constraints: dict):
    logger.info("[BACKGROUND TASK] Starting concurrent fetching job for task_id: %s", task_id)
    try:
        results = await fetch_flights_concurrently(constraints)
        logger.info("[BACKGROUND TASK] Concurrent fetching job completed for task_id: %s", task_id)
        
        # Print results to the terminal to verify the concurrency and retry logic
        print("\n" + "="*85, flush=True)
        print(f"AGGREGATED FLIGHT DATA FOR TASK {task_id}:", flush=True)
        print(json.dumps(results, indent=2), flush=True)
        print("="*85 + "\n", flush=True)
        
    except Exception as exc:
        logger.exception("[BACKGROUND TASK ERROR] Failed during concurrent fetching for task_id %s: %s", task_id, exc)

@router.post("/orchestrate", status_code=status.HTTP_202_ACCEPTED)
async def start_orchestration(request: OrchestratorRequest, background_tasks: BackgroundTasks):
    # 1. Generate a unique ID for this job
    task_id = str(uuid.uuid4())
    
    # 2. Add the concurrent fetch task to FastAPI BackgroundTasks
    background_tasks.add_task(run_fetcher_background, task_id, request.constraints)
    
    # 3. Immediately return 202 Accepted with task_id
    return {
        "task_id": task_id,
        "status": "ACCEPTED",
        "message": "Task accepted. Running flight fetch concurrently in the background."
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