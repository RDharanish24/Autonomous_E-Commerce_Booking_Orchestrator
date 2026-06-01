from fastapi import APIRouter, HTTPException
from models.schemas import OrchestratorRequest, TaskRecord, TaskStatus
from tasks.worker import run_orchestration_task
import uuid
# Inside api/routes.py -> start_orchestration
from services.dynamodb_service import create_task_record

# ... setup record ...


router = APIRouter()

@router.post("/orchestrate", response_model=TaskRecord)
async def start_orchestration(request: OrchestratorRequest):
    # 1. Generate a unique ID for this job
    task_id = str(uuid.uuid4())
    
    # 2. Create the initial database record (Status: PENDING)
    record = TaskRecord(
        task_id=task_id,
        status=TaskStatus.PENDING,
        request=request
    )
    
    # TODO: Save 'record' to DynamoDB here
    
    # 3. Fire off the background job. 
    # .delay() is Celery's magic method to push this to Redis.
    run_orchestration_task.delay(task_id, request.model_dump())
    
    # 4. Immediately return the tracking ID to the frontend
    return record

@router.get("/status/{task_id}", response_model=TaskRecord)
async def get_task_status(task_id: str):
    # TODO: Fetch the current state from DynamoDB
    # If the task isn't found, raise a 404
    pass

success = create_task_record(record)
if not success:
    raise HTTPException(status_code=500, detail="Database failure")