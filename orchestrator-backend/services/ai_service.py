import asyncio
from google import genai
from google.genai import types

from core.config import settings
from models.schemas import OrchestratorRequest, VendorOption, AIDecision

class AIService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("[AI ERROR] GEMINI_API_KEY is missing from settings.")
        
        # Initialize the Google GenAI Client
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash"

    def _construct_prompt(self, request: OrchestratorRequest, options: list[VendorOption]) -> str:
        """Helper to build the evaluation prompt."""
        options_serialized = [opt.model_dump(mode='json') for opt in options]
        
        return f"""
        You are the core decision engine for an Autonomous E-Commerce & Booking Orchestrator.
        Your task is to evaluate multiple vendor options against a user's goal and hard constraints, 
        and select the single best option.

        User Goal: {request.goal}
        User Constraints: {request.constraints}

        Available Vendor Options:
        {options_serialized}

        Instructions:
        1. Analyze the price, availability, and metadata of each vendor option against the user's constraints.
        2. Identify the winning option that best satisfies the constraints.
        3. If multiple options satisfy the constraints, select the most optimal one.
        4. Provide clear, objective reasoning for your decision.
        """

    async def evaluate_options(self, request: OrchestratorRequest, options: list[VendorOption]) -> AIDecision:
        """
        Submits constraints to Gemini, enforcing a structured output matching AIDecision.
        """
        if not options:
            raise ValueError("Cannot evaluate options because the vendor list is empty.")

        prompt = self._construct_prompt(request, options)

        # Force Gemini to return valid JSON matching our Pydantic model
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AIDecision,
            temperature=0.1, 
        )

        try:
            # Prevent the synchronous SDK call from blocking the async worker loop
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
            )

            # Parse the guaranteed JSON string directly back into the Pydantic model
            return AIDecision.model_validate_json(response.text)

        except Exception as e:
            print(f"[AI ERROR] Gemini evaluation failed: {e}")
            raise e