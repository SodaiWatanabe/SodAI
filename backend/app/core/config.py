from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SodAI API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://sodai_app:sodai@localhost:5432/sodai"

    auth_issuer: str = "http://localhost:3000"
    auth_audience: str = "http://localhost:3000"
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_jwt_algorithm: str = "EdDSA"
    auth_jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)
    auth_jwks_cache_seconds: int = Field(default=3600, ge=30, le=86400)
    auth_jwks_timeout_seconds: float = Field(default=5.0, gt=0, le=30)

    model_config = SettingsConfigDict(
        env_file=".env",
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
