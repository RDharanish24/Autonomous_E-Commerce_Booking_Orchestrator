import os
from celery import Celery

# We use Redis as both the message broker and the result backend.
# For local dev, a simple Docker container on port 6379 works perfectly.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "orchestrator_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.worker"] # Tells Celery where to look for tasks
)

# Optional: Route our heavy AI tasks to a specific queue
celery_app.conf.task_routes = {
    "tasks.worker.run_orchestration_task": {"queue": "orchestrator_queue"}
}