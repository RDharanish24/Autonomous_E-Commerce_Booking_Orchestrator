from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AWS DynamoDB
    DYNAMODB_ENDPOINT_URL: Optional[str] = None
    DYNAMODB_TABLE_NAME: str = "OrchestratorTasks"
    AWS_REGION: str = "us-east-1"
    
    # AI Engine
    GEMINI_API_KEY: str
    
    # Mock Vendors
    VENDOR_A_URL: str = "http://localhost:8001/api/v1/vendor-a"
    VENDOR_B_URL: str = "http://localhost:8001/api/v1/vendor-b"
    VENDOR_C_URL: str = "http://localhost:8001/api/v1/vendor-c"

    class Config:
        env_file = ".env"

# Instantiate globally so other modules can just import `settings`
settings = Settings()