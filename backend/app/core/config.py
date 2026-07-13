from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sodai_contracts.inference import (
    MIN_INFERENCE_JOB_TIMEOUT_SECONDS,
    InferenceNamespace,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    app_name: str = "SodAI API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:3000"
    guest_cookie_secure: bool = False

    database_url: str = "postgresql+asyncpg://sodai_app:sodai@localhost:5432/sodai"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_password: str | None = None
    model_root: Path = Field(
        default=REPOSITORY_ROOT / "var" / "models",
        validation_alias=AliasChoices("SODAI_MODEL_ROOT", "model_root"),
    )
    inference_namespace: str = "sodai:inference"
    inference_event_claim_idle_ms: int = Field(default=2_000, ge=500, le=60_000)
    inference_job_timeout_seconds: int = Field(
        default=300, ge=MIN_INFERENCE_JOB_TIMEOUT_SECONDS, le=3600
    )
    inference_model_active_limit: int = Field(default=32, ge=1, le=10_000)
    inference_guest_model_active_limit: int = Field(default=1, ge=1, le=100)
    inference_reconciliation_interval_seconds: float = Field(default=5, gt=0, le=60)
    inference_status_timeout_seconds: float = Field(default=1, gt=0, le=10)
    inference_status_cache_seconds: float = Field(default=2, ge=0, le=30)

    auth_issuer: str = "http://localhost:3000"
    auth_audience: str = "http://localhost:3000"
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_jwt_algorithm: str = "EdDSA"
    auth_jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)
    auth_jwks_cache_seconds: int = Field(default=3600, ge=30, le=86400)
    auth_jwks_timeout_seconds: float = Field(default=5.0, gt=0, le=30)

    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def require_async_postgresql(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        return value

    @field_validator("auth_issuer", "auth_audience", "auth_jwks_url")
    @classmethod
    def strip_trailing_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("authentication endpoint settings must not be empty")
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        return value

    @field_validator("inference_namespace")
    @classmethod
    def validate_inference_namespace(cls, value: str) -> str:
        return InferenceNamespace(value.strip()).prefix

    @property
    def inference_keys(self) -> InferenceNamespace:
        return InferenceNamespace(self.inference_namespace)

    @field_validator("model_root")
    @classmethod
    def resolve_model_root_from_repository(cls, value: Path) -> Path:
        return (value if value.is_absolute() else REPOSITORY_ROOT / value).resolve()

    @field_validator("auth_jwt_algorithm")
    @classmethod
    def forbid_symmetric_jwt_algorithms(cls, value: str) -> str:
        value = value.strip()
        allowed = {"EdDSA", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512", "RS256"}
        if value not in allowed:
            raise ValueError("AUTH_JWT_ALGORITHM must be a supported asymmetric algorithm")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
