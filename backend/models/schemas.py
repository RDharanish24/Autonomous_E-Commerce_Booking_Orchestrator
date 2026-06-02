from pydantic import BaseModel, Field
from typing import Dict, Any
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    FETCHING = "FETCHING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class OrchestratorRequest(BaseModel):
    goal: str = Field(..., example="Book a flight to NYC")
    constraints: Dict[str, Any] = Field(default_factory=dict)

class VendorOption(BaseModel):
    vendor_id: str
    service_name: str
    price: float
    currency: str = "USD"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AIDecision(BaseModel):
    selected_vendor_id: str
    total_cost: float
    confidence_score: float
    reasoning: str