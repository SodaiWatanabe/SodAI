from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.credits import (
    FREE_CREDIT_ALLOWANCE_POLICY,
    CreditAllowanceLot,
    FreeCreditAllowance,
    FreeCreditAllowancePolicy,
)
from app.repositories.credits import CreditLedgerRepository


class FreeCreditAllowanceService:
    """Starts and reads on-demand seven-day free-credit cycles."""

    def __init__(
        self,
        session: AsyncSession,
        policy: FreeCreditAllowancePolicy = FREE_CREDIT_ALLOWANCE_POLICY,
    ) -> None:
        self._ledger = CreditLedgerRepository(session)
        self._policy = policy

    async def current(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> tuple[FreeCreditAllowance | None, datetime]:
        effective_at = now or await self._ledger.database_now()
        account_id = await self._ledger.user_wallet(user_id)
        if account_id is None:
            return None, effective_at
        allowance_lot = await self._ledger.active_free_allowance(
            account_id,
            now=effective_at,
        )
        if allowance_lot is None:
            return None, effective_at
        return await self._summary(user_id, allowance_lot, effective_at), effective_at

    async def start_for_request(
        self,
        user_id: UUID,
        execution_id: UUID,
        *,
        now: datetime | None = None,
    ) -> tuple[FreeCreditAllowance, datetime]:
        account_id = await self._ledger.ensure_locked_user_wallet(user_id)
        effective_at = now or await self._ledger.database_now()
        allowance_lot = await self._ledger.active_free_allowance(
            account_id,
            now=effective_at,
        )
        if allowance_lot is None:
            window = self._policy.start_window(effective_at)
            grant = await self._ledger.grant_free_allowance_on_locked_wallet(
                user_id,
                account_id,
                execution_id,
                self._policy.amount,
                expires_at=window.expires_at,
                now=effective_at,
            )
            allowance_lot = CreditAllowanceLot(
                lot_id=grant.lot_id,
                starts_at=window.starts_at,
                expires_at=window.expires_at,
            )
        return await self._summary(user_id, allowance_lot, effective_at), effective_at

    async def _summary(
        self,
        user_id: UUID,
        allowance_lot: CreditAllowanceLot,
        now: datetime,
    ) -> FreeCreditAllowance:
        lot = await self._ledger.lot_balance(user_id, allowance_lot.lot_id, now=now)
        return FreeCreditAllowance(
            limit=lot.limit,
            used=lot.used,
            reserved=lot.reserved,
            remaining=lot.remaining,
            starts_at=allowance_lot.starts_at,
            expires_at=allowance_lot.expires_at,
        )
