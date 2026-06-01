import asyncio
import json
import redis
from core.celery_app import celery_app
from core.config import settings
from services.dynamodb_service import update_task_state
from services.vendor_service import VendorService
from services.ai_service import AIService
from models.schemas import TaskStatus, OrchestratorRequest

# 1. Module-Level Initializations
# Initialize the AI service once so the connection is reused across tasks
ai_service = AIService()

# Synchronous Redis client for the Celery worker to broadcast WebSocket updates
sync_redis = redis.Redis.from_url(settings.REDIS_URL)

def broadcast_update(task_id: str, status: str, payload: dict = None):
    """Publishes a real-time update to the FastAPI WebSocket listeners."""
    message = {
        "task_id": task_id,
        "status": status,
        "payload": payload or {}
    }
    # Broadcast to a specific channel unique to this task
    sync_redis.publish(f"task_updates:{task_id}", json.dumps(message))

async def _orchestrate_async(task_id: str, request_data: dict):
    """
    The core asynchronous pipeline executing the 3 phases: Fetching, Evaluating, and Completion.
    """
    print(f"[WORKER] Starting orchestration for Task ID: {task_id}")
    
    # 1. Parse the incoming request data back into our API schema
    try:
        request = OrchestratorRequest(**request_data)
    except Exception as e:
        print(f"[WORKER ERROR] Invalid request payload: {e}")
        update_task_state(task_id, TaskStatus.FAILED, error_message="Invalid request payload.")
        broadcast_update(task_id, TaskStatus.FAILED.value, {"error": "Invalid request payload."})
        return

    # Initialize the vendor service (handles HTTP connections)
    vendor_service = VendorService()

    try:
        # ---------------------------------------------------------
        # PHASE 1: FETCHING
        # ---------------------------------------------------------
        update_task_state(task_id, TaskStatus.FETCHING)
        broadcast_update(task_id, TaskStatus.FETCHING.value)
        print(f"[WORKER] Fetching options for constraints: {request.constraints}")
        
        vendor_options = await vendor_service.fetch_all_vendors_concurrently(request.constraints)
        
        if not vendor_options:
            raise ValueError("All vendors failed or returned zero viable options.")

        # Serialize options to save to DynamoDB for the audit trail
        serialized_options = [opt.model_dump(mode='json') for opt in vendor_options]

        # ---------------------------------------------------------
        # PHASE 2: EVALUATING
        # ---------------------------------------------------------
        update_task_state(
            task_id, 
            TaskStatus.EVALUATING, 
            vendor_results=serialized_options
        )
        broadcast_update(task_id, TaskStatus.EVALUATING.value, {"options_found": len(vendor_options)})
        print(f"[WORKER] Evaluating {len(vendor_options)} options via AI...")

        ai_decision = await ai_service.evaluate_options(request, vendor_options)

        # ---------------------------------------------------------
        # PHASE 3: COMPLETED
        # ---------------------------------------------------------
        final_decision_dict = ai_decision.model_dump(mode='json')
        update_task_state(
            task_id, 
            TaskStatus.COMPLETED, 
            final_decision=final_decision_dict
        )
        broadcast_update(task_id, TaskStatus.COMPLETED.value, {"decision": final_decision_dict})
        print(f"[WORKER] Task {task_id} completed successfully. Winner: {ai_decision.selected_vendor_id}")

    except Exception as e:
        # Global Catch-All: Ensure the database and frontend reflect a failure if the pipeline crashes
        print(f"[WORKER ERROR] Pipeline failed for {task_id}: {str(e)}")
        update_task_state(task_id, TaskStatus.FAILED, error_message=str(e))
        broadcast_update(task_id, TaskStatus.FAILED.value, {"error": str(e)})
        
    finally:
        # Always close HTTP connections gracefully to prevent memory leaks
        await vendor_service.close()


@celery_app.task(name="tasks.worker.run_orchestration_task")
def run_orchestration_task(task_id: str, request_data: dict):
    """
    Synchronous wrapper required by Celery.
    This creates an isolated event loop to run our high-performance async code.
    """
    asyncio.run(_orchestrate_async(task_id, request_data))