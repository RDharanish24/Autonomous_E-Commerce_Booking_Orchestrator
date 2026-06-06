"""
Phase 3: AI Flight Evaluator Service
=====================================
Uses the Google Gemini API (gemini-2.5-flash) to evaluate aggregated flight
options against user constraints and return a strict structured JSON decision.

The service enforces output structure via Pydantic schema passed directly to
the Gemini API's response_schema parameter, guaranteeing valid JSON output.

Error Handling:
    All LLM calls are wrapped in try-except. On any failure (API timeout,
    network error, validation failure), a FallbackDecision is returned
    with requires_human_review=True so the system degrades gracefully.
"""

import json
import logging
from typing import Union

from google import genai
from google.genai import types

from core.config import settings
from models.schemas import FlightEvaluationDecision, FallbackDecision

logger = logging.getLogger(__name__)

# ── System Prompt ──
# Concise, focused instruction set. No creativity, no suggestions —
# pure constraint-matching evaluation engine.
SYSTEM_PROMPT = (
    "You are a strict flight evaluation engine for an autonomous booking system. "
    "You receive a list of flight options and user constraints. "
    "Your ONLY job is to:\n"
    "1. Compare each flight against ALL user constraints.\n"
    "2. Select the single best flight that satisfies the most constraints.\n"
    "3. Assign a unique selected_flight_id using the format: '{vendor}_{index}' "
    "(e.g., 'vendor-alpha_0' for the first flight from vendor-alpha).\n"
    "4. Set meets_all_constraints to true ONLY if every single constraint is met.\n"
    "5. If no flight meets all constraints, select the closest match and set "
    "meets_all_constraints to false.\n"
    "Do NOT add commentary. Do NOT suggest alternatives. "
    "Return ONLY the structured decision."
)


def _build_evaluation_prompt(constraints: str, flights: list[dict]) -> str:
    """Constructs the user-facing evaluation prompt with flight data and constraints."""
    return (
        f"User Constraints:\n{constraints}\n\n"
        f"Available Flight Options:\n{json.dumps(flights, indent=2)}\n\n"
        "Evaluate all options against the constraints and select the best flight."
    )


def evaluate_flights(
    constraints: str,
    flights: list[dict],
) -> Union[FlightEvaluationDecision, FallbackDecision]:
    """
    Evaluates aggregated flight data against user constraints using Gemini AI.

    Args:
        constraints: The user's constraint string (e.g., "budget under $400, 
                     no more than 1 layover, morning departure preferred").
        flights: JSON list of aggregated flight dicts from Phase 2 vendor fetching.

    Returns:
        FlightEvaluationDecision on success — strict structured JSON from Gemini.
        FallbackDecision on failure — safe state flagging human review.
    """
    if not flights:
        logger.warning("[AI EVALUATOR] No flights to evaluate. Returning fallback.")
        return FallbackDecision(
            reasoning="No flight options were provided for evaluation.",
            error_detail="Empty flight list received from Phase 2 aggregation."
        )

    # ── Initialize the Gemini client ──
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error("[AI EVALUATOR] Failed to initialize Gemini client: %s", e)
        return FallbackDecision(
            reasoning="AI service initialization failed. Human review required.",
            error_detail=str(e)
        )

    # ── Build the prompt ──
    user_prompt = _build_evaluation_prompt(constraints, flights)

    # ── Configure structured output ──
    # Passing the Pydantic schema to response_schema guarantees that Gemini
    # returns JSON matching FlightEvaluationDecision exactly.
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=FlightEvaluationDecision,
        temperature=0.0,  # Deterministic evaluation — no randomness
    )

    # ── Call Gemini API with full error handling ──
    try:
        logger.info("[AI EVALUATOR] Sending %d flights to Gemini for evaluation...", len(flights))

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=config,
        )

        # Parse the schema-enforced JSON response into our Pydantic model
        decision = FlightEvaluationDecision.model_validate_json(response.text)

        logger.info(
            "[AI EVALUATOR] ✓ Decision: flight=%s vendor=%s cost=$%.2f meets_all=%s",
            decision.selected_flight_id,
            decision.vendor_name,
            decision.total_cost,
            decision.meets_all_constraints,
        )
        return decision

    except Exception as e:
        # ── Safe State Fallback ──
        # Catches: API timeout, network error, rate limiting, validation failure,
        # malformed response, or any unexpected exception.
        logger.error("[AI EVALUATOR] Gemini evaluation failed: %s", e)
        return FallbackDecision(
            reasoning=(
                f"AI evaluation failed. Human review required "
                f"for {len(flights)} flight option(s)."
            ),
            error_detail=str(e),
        )
