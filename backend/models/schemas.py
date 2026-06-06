from pydantic import BaseModel, Field
from typing import Dict, Any,Optional
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
    client_id: Optional[str] = Field(default=None, description="WebSocket client ID for real-time updates")

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


# ── Phase 3: Structured Output Schemas for Gemini AI Evaluator ──

class FlightEvaluationDecision(BaseModel):
    """Strict structured output schema enforced on the Gemini LLM response.
    
    Passed directly to the google-genai SDK via response_schema to guarantee
    that the model returns valid JSON matching this exact shape.
    """
    selected_flight_id: str = Field(
        ..., description="Unique identifier of the winning flight option (e.g. 'vendor-alpha_flight_1')"
    )
    vendor_name: str = Field(
        ..., description="Name of the vendor offering the selected flight"
    )
    total_cost: float = Field(
        ..., description="Total cost of the selected flight in USD"
    )
    reasoning: str = Field(
        ..., description="Brief explanation of why this flight won based on the user's constraints"
    )
    meets_all_constraints: bool = Field(
        ..., description="Whether the selected flight satisfies every user constraint"
    )


class FallbackDecision(BaseModel):
    """Safe-state fallback returned when the AI evaluation pipeline fails.
    
    Signals to downstream consumers (DynamoDB, frontend) that automatic
    evaluation was unsuccessful and a human operator must review the options.
    """
    selected_flight_id: str = "NONE"
    vendor_name: str = "N/A"
    total_cost: float = 0.0
    reasoning: str = Field(
        ..., description="Explanation of why the AI evaluation failed"
    )
    meets_all_constraints: bool = False
    requires_human_review: bool = True
    error_detail: str = Field(
        ..., description="Technical error message from the failed LLM call"
    )