from __future__ import annotations

import base64
from datetime import datetime
from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session_factory
from app.domain.humans import HumanAnswerDetail, HumanAnswerPage
from app.repositories.human_answers import SqlAlchemyHumanAnswerHistoryRepository


class HumanAnswerHistoryService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def page(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> HumanAnswerPage:
        parsed_cursor = self._parse_cursor(cursor) if cursor else None
        async with self._session_factory() as session:
            items, has_more = await SqlAlchemyHumanAnswerHistoryRepository(session).page(
                user_id, limit=limit, cursor=parsed_cursor
            )
        next_cursor = None
        if has_more and items:
            last = items[-1]
            raw_cursor = f"{last.answered_at.isoformat()}|{last.execution_id}".encode()
            next_cursor = base64.urlsafe_b64encode(raw_cursor).decode("ascii").rstrip("=")
        return HumanAnswerPage(items, next_cursor)

    async def get(self, user_id: UUID, execution_id: UUID) -> HumanAnswerDetail:
        async with self._session_factory() as session:
            return await SqlAlchemyHumanAnswerHistoryRepository(session).get(
                user_id,
                execution_id,
            )

    @staticmethod
    def _parse_cursor(value: str) -> tuple[datetime, UUID]:
        try:
            padding = "=" * (-len(value) % 4)
            decoded = base64.b64decode(
                value + padding,
                altchars=b"-_",
                validate=True,
            ).decode("utf-8")
            timestamp, execution_id = decoded.rsplit("|", 1)
            answered_at = datetime.fromisoformat(timestamp)
            if answered_at.tzinfo is None:
                raise ValueError
            return answered_at, UUID(execution_id)
        except (TypeError, ValueError) as error:
            raise ValueError("invalid Human answer cursor") from error


@lru_cache
def get_human_answer_history_service() -> HumanAnswerHistoryService:
    return HumanAnswerHistoryService(get_session_factory())
