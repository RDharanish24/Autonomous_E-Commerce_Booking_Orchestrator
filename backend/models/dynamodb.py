from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from models.schemas import TaskStatus, OrchestratorRequest, VendorOption, AIDecision, FlightEvaluationDecision

class TaskRecord(BaseModel):
    """Represents the single-table schema stored in AWS DynamoDB."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Nested Payloads
    request: OrchestratorRequest
    vendor_results: Optional[List[VendorOption]] = None
    final_decision: Optional[AIDecision] = None
    flight_evaluation: Optional[FlightEvaluationDecision] = None  # Phase 3 structured AI output
    error_message: Optional[str] = None