from fastapi import FastAPI
from api.routes import router
from api.mock_vendors import router as mock_router
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)

app = FastAPI(
    title="Autonomous E-Commerce Orchestrator",
    description="AI-powered API for autonomous service booking.",
    version="1.0.0"
)

# Mount our routes
app.include_router(router, prefix="/api/v1")
app.include_router(mock_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "Systems operational", "message": "Backend API is running"}