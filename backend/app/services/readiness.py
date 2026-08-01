import asyncio

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings, get_settings
from app.db.session import get_engine


class ReadinessService:
    def __init__(self, settings: Settings, engine: AsyncEngine) -> None:
        self._settings = settings
        self._engine = engine

    async def check(self) -> None:
        redis = Redis.from_url(
            self._settings.redis_url,
            password=self._settings.redis_password,
            decode_responses=True,
        )
        try:
            await asyncio.wait_for(
                asyncio.gather(self._check_database(), redis.ping()),
                timeout=self._settings.readiness_timeout_seconds,
            )
        finally:
            await redis.aclose()

    async def _check_database(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("select 1"))


def get_readiness_service() -> ReadinessService:
    return ReadinessService(get_settings(), get_engine())
