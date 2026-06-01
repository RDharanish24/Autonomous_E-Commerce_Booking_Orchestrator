from fastapi import FastAPI
from api.routes import router

app = FastAPI(
    title="Autonomous E-Commerce Orchestrator",
    description="AI-powered API for autonomous service booking.",
    version="1.0.0"
)

# Mount our routes
app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "Systems operational", "queue": "Redis active"}