"""
core/config.py

Centralised configuration for the Autonomous E-Commerce & Booking Orchestrator.

All values are loaded from environment variables (or a .env file via
python-dotenv).  Every consumer in the codebase imports the single
`settings` singleton — never os.getenv() directly.

Usage:
    from core.config import settings

    print(settings.REDIS_URL)
    print(settings.AWS_REGION)
"""

import logging
import sys
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings Model
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.

    Sections:
        1. Application
        2. Redis / Celery broker
        3. AWS / DynamoDB
        4. AI Engine (Gemini / Groq / Ollama)
        5. Vendor Mock APIs
        6. WebSocket
        7. Logging
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,       # ENV_VAR names are uppercase by convention
        extra="ignore",            # Silently ignore unknown env vars
        populate_by_name=True,
    )

    # ------------------------------------------------------------------ #
    # 1. Application
    # ------------------------------------------------------------------ #

    APP_NAME: str = Field(
        default="Autonomous E-Commerce & Booking Orchestrator",
        description="Human-readable application name.",
    )
    APP_ENV: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment. Controls debug flags and log verbosity.",
    )
    APP_HOST: str = Field(default="0.0.0.0", description="Uvicorn bind host.")
    APP_PORT: int = Field(default=8000, ge=1, le=65535, description="Uvicorn bind port.")
    DEBUG: bool = Field(
        default=False,
        description="Enable FastAPI debug mode. Never True in production.",
    )
    SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="Used for signing internal tokens. Must be overridden in production.",
    )
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="CORS allowed origins. Add your frontend URL here.",
    )

    # ------------------------------------------------------------------ #
    # 2. Redis / Celery Broker
    # ------------------------------------------------------------------ #

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL used by both Celery broker and pub/sub.",
    )
    CELERY_BROKER_URL: str = Field(
        default="",
        description=(
            "Celery broker URL. Defaults to REDIS_URL if left empty. "
            "Set explicitly to use a different broker (e.g. RabbitMQ)."
        ),
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="",
        description="Celery result backend URL. Defaults to REDIS_URL if left empty.",
    )
    CELERY_TASK_TIMEOUT: int = Field(
        default=300,
        ge=10,
        description="Hard time limit (seconds) for a single Celery task before it is killed.",
    )
    CELERY_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        description="Maximum number of Celery task-level retries on unexpected failure.",
    )

    # ------------------------------------------------------------------ #
    # 3. AWS / DynamoDB
    # ------------------------------------------------------------------ #

    AWS_REGION: str = Field(
        default="us-east-1",
        description="AWS region where the DynamoDB table is provisioned.",
    )
    AWS_ACCESS_KEY_ID: str = Field(
        default="",
        description="AWS access key. Leave empty when using IAM roles / instance profiles.",
    )
    AWS_SECRET_ACCESS_KEY: str = Field(
        default="",
        description="AWS secret key. Leave empty when using IAM roles / instance profiles.",
    )
    DYNAMODB_TABLE_NAME: str = Field(
        default="orchestrator_tasks",
        description="DynamoDB table name for task records.",
    )
    DYNAMODB_ENDPOINT_URL: str = Field(
        default="",
        description=(
            "Override DynamoDB endpoint. Set to 'http://localhost:8001' "
            "when using DynamoDB Local for development."
        ),
    )

    # ------------------------------------------------------------------ #
    # 4. AI Engine
    # ------------------------------------------------------------------ #

    AI_PROVIDER: Literal["gemini", "groq", "ollama"] = Field(
        default="gemini",
        description="Which LLM provider to use for the decision engine.",
    )

    # --- Gemini ---
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key. Required when AI_PROVIDER='gemini'.",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model identifier.",
    )

    # --- Groq ---
    GROQ_API_KEY: str = Field(
        default="",
        description="Groq API key. Required when AI_PROVIDER='groq'.",
    )
    GROQ_MODEL: str = Field(
        default="llama3-8b-8192",
        description="Groq model identifier.",
    )

    # --- Ollama (local, free-tier friendly) ---
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL. Required when AI_PROVIDER='ollama'.",
    )
    OLLAMA_MODEL: str = Field(
        default="llama3",
        description="Ollama model name to pull and run locally.",
    )

    # --- Shared AI settings ---
    AI_MAX_TOKENS: int = Field(
        default=1024,
        ge=64,
        le=8192,
        description="Maximum tokens the LLM may generate per decision call.",
    )
    AI_TEMPERATURE: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description=(
            "LLM temperature. Low value (≤0.3) is recommended for structured "
            "JSON output to reduce hallucination risk."
        ),
    )
    AI_REQUEST_TIMEOUT: int = Field(
        default=30,
        ge=5,
        description="HTTP timeout (seconds) for AI provider API calls.",
    )

    # ------------------------------------------------------------------ #
    # 5. Vendor Mock APIs
    # ------------------------------------------------------------------ #

    VENDOR_REQUEST_TIMEOUT: int = Field(
        default=10,
        ge=1,
        description="Per-request HTTP timeout (seconds) when calling mock vendor APIs.",
    )
    VENDOR_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts per vendor before marking it as failed.",
    )
    VENDOR_RETRY_BACKOFF_BASE: float = Field(
        default=0.5,
        ge=0.1,
        description="Base delay (seconds) for exponential backoff: delay = base * 2^attempt.",
    )
    VENDOR_RETRY_BACKOFF_MAX: float = Field(
        default=10.0,
        ge=1.0,
        description="Maximum backoff delay cap (seconds).",
    )
    # Simulated failure rate for mock vendors (0.0 = never fail, 1.0 = always fail)
    VENDOR_MOCK_FAILURE_RATE: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description=(
            "Probability (0–1) that a mock vendor request simulates a 500 error. "
            "Set to 0.0 in production (real APIs don't need this)."
        ),
    )
    VENDOR_MOCK_MAX_DELAY_SECONDS: float = Field(
        default=3.0,
        ge=0.0,
        description="Maximum simulated network delay (seconds) for mock vendors.",
    )

    # ------------------------------------------------------------------ #
    # 6. WebSocket
    # ------------------------------------------------------------------ #

    WS_HEARTBEAT_INTERVAL: int = Field(
        default=30,
        ge=5,
        description="Seconds between server-side WebSocket keep-alive pings.",
    )
    WS_MAX_CONNECTIONS_PER_TASK: int = Field(
        default=10,
        ge=1,
        description="Maximum simultaneous WebSocket connections allowed per task_id.",
    )
    REDIS_PUBSUB_POLL_INTERVAL: float = Field(
        default=0.05,
        ge=0.01,
        description="Seconds between Redis pub/sub poll ticks inside the WebSocket loop.",
    )

    # ------------------------------------------------------------------ #
    # 7. Logging
    # ------------------------------------------------------------------ #

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Root logger level.",
    )
    LOG_FORMAT: Literal["json", "text"] = Field(
        default="text",
        description=(
            "Log output format. Use 'json' in production for structured log ingestion "
            "(CloudWatch, Datadog). Use 'text' in development for readability."
        ),
    )

    # ================================================================== #
    # Validators
    # ================================================================== #

    @field_validator("SECRET_KEY")
    @classmethod
    def warn_default_secret_key(cls, v: str) -> str:
        if v == "change-me-in-production":
            logger.warning(
                "SECRET_KEY is set to the default placeholder. "
                "Override it with a strong random value in production."
            )
        return v

    @field_validator("DEBUG")
    @classmethod
    def no_debug_in_production(cls, v: bool, info) -> bool:
        # info.data may not have APP_ENV yet during field-by-field validation;
        # the model_validator below handles the cross-field check.
        return v

    @model_validator(mode="after")
    def apply_defaults_and_cross_field_checks(self) -> "Settings":
        # --- Celery broker/backend default to REDIS_URL ---
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL

        # --- Enforce DEBUG=False in production ---
        if self.APP_ENV == "production" and self.DEBUG:
            logger.warning(
                "DEBUG=True is not allowed in production. Forcing DEBUG=False."
            )
            self.DEBUG = False

        # --- Warn if required AI key is missing ---
        missing_key = False
        if self.AI_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            missing_key = True
        elif self.AI_PROVIDER == "groq" and not self.GROQ_API_KEY:
            missing_key = True
        elif self.AI_PROVIDER == "ollama" and not self.OLLAMA_BASE_URL:
            missing_key = True

        if missing_key:
            logger.warning(
                "AI provider '%s' is selected but its API key / URL is not configured. "
                "Set the appropriate variable in .env before running the worker.",
                self.AI_PROVIDER,
            )

        # --- Warn on missing AWS credentials (only if not using IAM role) ---
        if not self.AWS_ACCESS_KEY_ID and not self.AWS_SECRET_ACCESS_KEY:
            logger.debug(
                "AWS credentials not set via env vars. "
                "Assuming IAM role or instance profile is in use."
            )

        return self

    # ================================================================== #
    # Convenience properties
    # ================================================================== #

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def dynamodb_kwargs(self) -> dict:
        """
        Keyword arguments for boto3.resource('dynamodb', **kwargs).
        Injects endpoint_url only when DYNAMODB_ENDPOINT_URL is set
        (i.e. DynamoDB Local in dev).
        """
        kwargs: dict = {"region_name": self.AWS_REGION}
        if self.AWS_ACCESS_KEY_ID:
            kwargs["aws_access_key_id"] = self.AWS_ACCESS_KEY_ID
        if self.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_secret_access_key"] = self.AWS_SECRET_ACCESS_KEY
        if self.DYNAMODB_ENDPOINT_URL:
            kwargs["endpoint_url"] = self.DYNAMODB_ENDPOINT_URL
        return kwargs

    @property
    def active_ai_model(self) -> str:
        """Return the model identifier for the currently configured AI provider."""
        return {
            "gemini": self.GEMINI_MODEL,
            "groq": self.GROQ_MODEL,
            "ollama": self.OLLAMA_MODEL,
        }[self.AI_PROVIDER]


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Using @lru_cache means the .env file is read exactly once per process.
    In tests, call `get_settings.cache_clear()` before monkeypatching env vars.
    """
    _settings = Settings()
    logger.info(
        "Configuration loaded | env=%s | ai_provider=%s | debug=%s",
        _settings.APP_ENV,
        _settings.AI_PROVIDER,
        _settings.DEBUG,
    )
    return _settings


# Module-level singleton — import this everywhere.
settings: Settings = get_settings()


# ---------------------------------------------------------------------------
# Logging bootstrap (called once from main.py)
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    """
    Configure the root logger based on settings.LOG_LEVEL and settings.LOG_FORMAT.
    Call this exactly once at application startup in main.py.
    """
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    if settings.LOG_FORMAT == "json":
        # Minimal JSON formatter — swap for `python-json-logger` in production.
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"name":"%(name)s","message":"%(message)s"}'
        )
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy third-party loggers
    for noisy in ("botocore", "boto3", "urllib3", "httpx", "celery.utils"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.debug("Logging configured | level=%s | format=%s", settings.LOG_LEVEL, settings.LOG_FORMAT)