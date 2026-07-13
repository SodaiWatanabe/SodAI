from __future__ import annotations

import base64
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session_factory
from app.domain.credits import (
    CreditBalance,
    CreditGrant,
    CreditSourceKind,
    CreditTransactionPage,
)
from app.repositories.credits import CreditLedgerRepository


class CreditService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def balance(self, user_id: UUID) -> CreditBalance:
        async with self._session_factory() as session:
            return await CreditLedgerRepository(session).balance(user_id)

    async def transactions(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> CreditTransactionPage:
        parsed_cursor = self._parse_cursor(cursor) if cursor else None
        async with self._session_factory() as session:
            return await CreditLedgerRepository(session).transaction_page(
                user_id,
                limit=limit,
                cursor=parsed_cursor,
            )

    async def grant(
        self,
        user_id: UUID,
        amount: int,
        *,
        idempotency_key: str,
        source_kind: CreditSourceKind = CreditSourceKind.ADMIN,
        expires_at: datetime | None = None,
    ) -> CreditGrant:
        normalized_key = idempotency_key.strip()
        if not normalized_key:
            raise ValueError("idempotency key cannot be blank")
        async with self._session_factory() as session:
            grant = await CreditLedgerRepository(session).grant(
                user_id,
                amount,
                source_kind=source_kind,
                idempotency_key=normalized_key,
                expires_at=expires_at,
            )
            await session.commit()
            return grant

    async def expire_due(self, now: datetime | None = None, *, limit: int = 100) -> int:
        async with self._session_factory() as session:
            count = await CreditLedgerRepository(session).expire_due(
                now or datetime.now(timezone.utc),
                limit=limit,
            )
            await session.commit()
            return count

    @staticmethod
    def _parse_cursor(value: str) -> tuple[datetime, UUID]:
        try:
            padding = "=" * (-len(value) % 4)
            decoded = base64.b64decode(
                value + padding,
                altchars=b"-_",
                validate=True,
            ).decode("utf-8")
            timestamp, transaction_id = decoded.rsplit("|", 1)
            created_at = datetime.fromisoformat(timestamp)
            if created_at.tzinfo is None:
                raise ValueError
            return created_at, UUID(transaction_id)
        except (TypeError, ValueError) as error:
            raise ValueError("invalid credit transaction cursor") from error


@lru_cache
def get_credit_service() -> CreditService:
    return CreditService(get_session_factory())
