from __future__ import annotations

import base64
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import Select, func, or_, select, tuple_, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.credits import (
    CREDIT_ASSET_CODE,
    CREDIT_SCALE,
    EXPIRED_ACCOUNT_ID,
    ISSUANCE_ACCOUNT_ID,
    RESERVE_ACCOUNT_ID,
    REVENUE_ACCOUNT_ID,
    CreditAccountKind,
    CreditAllowanceLot,
    CreditBalance,
    CreditConsumptionKind,
    CreditGrant,
    CreditIdempotencyConflictError,
    CreditLotBalance,
    CreditReservationStatus,
    CreditSourceKind,
    CreditTransaction,
    CreditTransactionKind,
    CreditTransactionPage,
    InsufficientCreditsError,
)
from app.models.credits import (
    CreditAccountModel,
    CreditLotConsumptionModel,
    CreditLotModel,
    CreditPostingModel,
    CreditReservationAllocationModel,
    CreditTransactionModel,
    InferenceCreditReservationModel,
)


class CreditLedgerRepository:
    """Owns append-only credit movements inside a caller-controlled transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def balance(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> CreditBalance:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("credit balance time must be timezone-aware")
        account = await self._user_account(user_id)
        if account is None:
            return CreditBalance(CREDIT_ASSET_CODE, CREDIT_SCALE, 0, 0)
        available = await self._spendable_balance(account.id, now)
        reserved = await self._session.scalar(
            select(func.coalesce(func.sum(InferenceCreditReservationModel.reserved_amount), 0))
            .where(
                InferenceCreditReservationModel.owner_account_id == account.id,
                InferenceCreditReservationModel.created_at <= now,
                or_(
                    InferenceCreditReservationModel.finalized_at.is_(None),
                    InferenceCreditReservationModel.finalized_at > now,
                ),
            )
        )
        return CreditBalance(
            CREDIT_ASSET_CODE,
            CREDIT_SCALE,
            int(available or 0),
            int(reserved or 0),
        )

    async def grant(
        self,
        user_id: UUID,
        amount: int,
        *,
        source_kind: CreditSourceKind,
        idempotency_key: str,
        expires_at: datetime | None = None,
        now: datetime | None = None,
    ) -> CreditGrant:
        if amount <= 0:
            raise ValueError("credit grant amount must be positive")
        if now is not None and now.tzinfo is None:
            raise ValueError("credit grant time must be timezone-aware")
        if expires_at is not None:
            if expires_at.tzinfo is None:
                raise ValueError("credit expiration must be timezone-aware")

        key_hash = self._hash_key(f"grant:{idempotency_key}")
        await self._session.execute(
            select(func.pg_advisory_xact_lock(self._advisory_key(key_hash)))
        )
        existing = await self._session.scalar(
            select(CreditTransactionModel).where(
                CreditTransactionModel.idempotency_key_hash == key_hash
            )
        )
        if existing is not None:
            return await self._replay_grant(
                existing,
                user_id=user_id,
                amount=amount,
                source_kind=source_kind,
                expires_at=expires_at,
            )

        account = await self._ensure_locked_user_account(user_id)
        now = now or datetime.now(timezone.utc)
        if expires_at is not None and expires_at <= now:
            raise ValueError("credit expiration must be in the future")
        # The wallet lock serializes grant creation for this user. Rechecking the
        # key after acquiring it turns concurrent retries into a normal replay.
        existing = await self._session.scalar(
            select(CreditTransactionModel).where(
                CreditTransactionModel.idempotency_key_hash == key_hash
            )
        )
        if existing is not None:
            return await self._replay_grant(
                existing,
                user_id=user_id,
                amount=amount,
                source_kind=source_kind,
                expires_at=expires_at,
            )
        transaction = self._append_transaction(
            CreditTransactionKind.GRANT,
            key_hash=key_hash,
            reference_type="user_credit_grant",
            reference_id=account.id,
            postings={ISSUANCE_ACCOUNT_ID: -amount, account.id: amount},
            effective_at=now,
        )
        await self._session.flush()
        lot = CreditLotModel(
            owner_account_id=account.id,
            issuance_transaction_id=transaction.id,
            source_kind=source_kind.value,
            original_amount=amount,
            issued_at=now,
            expires_at=expires_at,
        )
        self._session.add(lot)
        await self._session.flush()
        return CreditGrant(transaction.id, lot.id, amount, replayed=False)

    async def lot_balance(
        self,
        user_id: UUID,
        lot_id: UUID,
        *,
        now: datetime | None = None,
    ) -> CreditLotBalance:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("credit lot balance time must be timezone-aware")
        lot = await self._session.scalar(
            select(CreditLotModel)
            .join(
                CreditAccountModel,
                CreditAccountModel.id == CreditLotModel.owner_account_id,
            )
            .where(
                CreditLotModel.id == lot_id,
                CreditAccountModel.owner_user_id == user_id,
                CreditAccountModel.asset_code == CREDIT_ASSET_CODE,
            )
        )
        if lot is None:
            raise RuntimeError("credit lot is missing or belongs to another user")
        used, reserved = await self._lot_usage(lot, now)
        remaining = lot.original_amount - used - reserved
        if remaining < 0:
            raise RuntimeError("credit lot usage exceeds its original amount")
        return CreditLotBalance(
            limit=lot.original_amount,
            used=used,
            reserved=reserved,
            remaining=remaining,
        )

    async def ensure_locked_user_wallet(self, user_id: UUID) -> UUID:
        return (await self._ensure_locked_user_account(user_id)).id

    async def user_wallet(self, user_id: UUID) -> UUID | None:
        account = await self._user_account(user_id)
        return account.id if account is not None else None

    async def database_now(self) -> datetime:
        now = await self._session.scalar(select(func.clock_timestamp()))
        if now is None or now.tzinfo is None:
            raise RuntimeError("database did not return a timezone-aware clock")
        return now

    async def active_free_allowance(
        self,
        account_id: UUID,
        *,
        now: datetime,
    ) -> CreditAllowanceLot | None:
        if now.tzinfo is None:
            raise ValueError("free credit allowance time must be timezone-aware")
        lot = await self._session.scalar(
            select(CreditLotModel)
            .join(
                CreditTransactionModel,
                CreditTransactionModel.id == CreditLotModel.issuance_transaction_id,
            )
            .where(
                CreditLotModel.owner_account_id == account_id,
                CreditLotModel.source_kind == CreditSourceKind.PROMOTIONAL.value,
                CreditLotModel.issued_at <= now,
                CreditLotModel.expires_at.is_not(None),
                CreditLotModel.expires_at > now,
                CreditTransactionModel.kind == CreditTransactionKind.GRANT.value,
                CreditTransactionModel.reference_type == "free_credit_allowance",
                CreditTransactionModel.reference_id == account_id,
            )
            .order_by(CreditLotModel.issued_at.desc(), CreditLotModel.id.desc())
            .limit(1)
        )
        if lot is None or lot.expires_at is None:
            return None
        return CreditAllowanceLot(
            lot_id=lot.id,
            starts_at=lot.issued_at,
            expires_at=lot.expires_at,
        )

    async def grant_free_allowance_on_locked_wallet(
        self,
        user_id: UUID,
        account_id: UUID,
        execution_id: UUID,
        amount: int,
        *,
        expires_at: datetime,
        now: datetime,
    ) -> CreditGrant:
        if amount <= 0:
            raise ValueError("free credit allowance must be positive")
        if now.tzinfo is None or expires_at.tzinfo is None:
            raise ValueError("free credit allowance times must be timezone-aware")
        if expires_at <= now:
            raise ValueError("free credit allowance expiration must be in the future")
        account = await self._session.get(CreditAccountModel, account_id)
        if account is None or account.owner_user_id != user_id:
            raise RuntimeError("locked credit account is missing or belongs to another user")

        key_hash = self._hash_key(f"grant:free-allowance:{execution_id}")
        existing = await self._session.scalar(
            select(CreditTransactionModel).where(
                CreditTransactionModel.idempotency_key_hash == key_hash
            )
        )
        if existing is not None:
            if (
                existing.reference_type != "free_credit_allowance"
                or existing.reference_id != account_id
            ):
                raise CreditIdempotencyConflictError
            return await self._replay_grant(
                existing,
                user_id=user_id,
                amount=amount,
                source_kind=CreditSourceKind.PROMOTIONAL,
                expires_at=expires_at,
            )

        transaction = self._append_transaction(
            CreditTransactionKind.GRANT,
            key_hash=key_hash,
            reference_type="free_credit_allowance",
            reference_id=account_id,
            postings={ISSUANCE_ACCOUNT_ID: -amount, account_id: amount},
            effective_at=now,
        )
        await self._session.flush()
        lot = CreditLotModel(
            owner_account_id=account_id,
            issuance_transaction_id=transaction.id,
            source_kind=CreditSourceKind.PROMOTIONAL.value,
            original_amount=amount,
            issued_at=now,
            expires_at=expires_at,
        )
        self._session.add(lot)
        await self._session.flush()
        return CreditGrant(transaction.id, lot.id, amount, replayed=False)

    async def reserve_inference(
        self,
        user_id: UUID,
        execution_id: UUID,
        amount: int,
        *,
        now: datetime | None = None,
    ) -> InferenceCreditReservationModel | None:
        if amount < 0:
            raise ValueError("credit reservation cannot be negative")
        if amount == 0:
            return None
        if now is not None and now.tzinfo is None:
            raise ValueError("credit reservation time must be timezone-aware")
        existing = await self._session.scalar(
            select(InferenceCreditReservationModel).where(
                InferenceCreditReservationModel.execution_reference_id == execution_id
            )
        )
        if existing is not None:
            return await self._validate_reservation(existing, user_id, amount)

        account = await self._locked_user_account(user_id)
        if account is None:
            raise InsufficientCreditsError
        # Another retry can finish while this call waits for the wallet lock.
        existing = await self._session.scalar(
            select(InferenceCreditReservationModel).where(
                InferenceCreditReservationModel.execution_reference_id == execution_id
            )
        )
        if existing is not None:
            return await self._validate_reservation(existing, user_id, amount)
        now = now or datetime.now(timezone.utc)
        if await self._spendable_balance(account.id, now) < amount:
            raise InsufficientCreditsError
        allocations = await self._allocate_lots(account.id, amount, now)
        transaction = self._append_transaction(
            CreditTransactionKind.RESERVE,
            key_hash=self._hash_key(f"inference-reserve:{execution_id}"),
            reference_type="inference_execution",
            reference_id=execution_id,
            postings={account.id: -amount, RESERVE_ACCOUNT_ID: amount},
            effective_at=now,
        )
        await self._session.flush()
        reservation = InferenceCreditReservationModel(
            execution_reference_id=execution_id,
            owner_account_id=account.id,
            status=CreditReservationStatus.HELD.value,
            reserved_amount=amount,
            settled_amount=0,
            reserve_transaction_id=transaction.id,
            created_at=now,
        )
        self._session.add(reservation)
        await self._session.flush()
        self._session.add_all(
            CreditReservationAllocationModel(
                reservation_id=reservation.id,
                lot_id=lot_id,
                amount=allocated,
            )
            for lot_id, allocated in allocations
        )
        await self._session.flush()
        return reservation

    async def finalize_inference(
        self,
        execution_id: UUID,
        charge: int,
        *,
        now: datetime | None = None,
    ) -> InferenceCreditReservationModel | None:
        if charge < 0:
            raise ValueError("inference charge cannot be negative")
        if now is not None and now.tzinfo is None:
            raise ValueError("inference finalization time must be timezone-aware")
        reservation = await self._session.scalar(
            select(InferenceCreditReservationModel)
            .where(
                InferenceCreditReservationModel.execution_reference_id == execution_id
            )
            .with_for_update()
        )
        if reservation is None:
            if charge:
                raise CreditIdempotencyConflictError
            return None
        if reservation.status != CreditReservationStatus.HELD.value:
            if reservation.settled_amount != charge:
                raise CreditIdempotencyConflictError
            return reservation
        if charge > reservation.reserved_amount:
            raise ValueError("inference charge cannot exceed the reservation")

        account = await self._session.scalar(
            select(CreditAccountModel)
            .where(CreditAccountModel.id == reservation.owner_account_id)
            .with_for_update()
        )
        if account is None:
            raise RuntimeError("credit reservation owner account is missing")
        now = now or datetime.now(timezone.utc)
        rows = (
            await self._session.execute(
                select(CreditReservationAllocationModel, CreditLotModel)
                .join(
                    CreditLotModel,
                    CreditLotModel.id == CreditReservationAllocationModel.lot_id,
                )
                .where(
                    CreditReservationAllocationModel.reservation_id == reservation.id
                )
                .order_by(
                    CreditLotModel.expires_at.asc().nullslast(),
                    CreditLotModel.issued_at,
                    CreditLotModel.id,
                )
                .with_for_update(of=CreditLotModel)
            )
        ).all()

        remaining_charge = charge
        returned = 0
        expired = 0
        consumptions: list[tuple[UUID, CreditConsumptionKind, int]] = []
        for allocation, lot in rows:
            settled = min(allocation.amount, remaining_charge)
            if settled:
                consumptions.append((lot.id, CreditConsumptionKind.SETTLE, settled))
                remaining_charge -= settled
            remainder = allocation.amount - settled
            if not remainder:
                continue
            if lot.expires_at is not None and lot.expires_at <= now:
                expired += remainder
                consumptions.append((lot.id, CreditConsumptionKind.EXPIRE, remainder))
            else:
                returned += remainder
        if remaining_charge:
            raise RuntimeError("credit reservation allocations do not cover the charge")

        postings = {RESERVE_ACCOUNT_ID: -reservation.reserved_amount}
        if charge:
            postings[REVENUE_ACCOUNT_ID] = charge
        if returned:
            postings[account.id] = returned
        if expired:
            postings[EXPIRED_ACCOUNT_ID] = expired
        transaction_kind = (
            CreditTransactionKind.SETTLE if charge else CreditTransactionKind.RELEASE
        )
        transaction = self._append_transaction(
            transaction_kind,
            key_hash=self._hash_key(f"inference-finalize:{execution_id}"),
            reference_type="inference_execution",
            reference_id=execution_id,
            postings=postings,
            effective_at=now,
        )
        await self._session.flush()
        for lot_id, kind, consumed in consumptions:
            self._session.add(
                CreditLotConsumptionModel(
                    lot_id=lot_id,
                    transaction_id=transaction.id,
                    kind=kind.value,
                    amount=consumed,
                )
            )
        reservation.status = (
            CreditReservationStatus.SETTLED.value
            if charge
            else CreditReservationStatus.RELEASED.value
        )
        reservation.settled_amount = charge
        reservation.final_transaction_id = transaction.id
        reservation.finalized_at = now
        await self._session.flush()
        return reservation

    async def expire_due(self, now: datetime, *, limit: int = 100) -> int:
        if now.tzinfo is None:
            raise ValueError("expiration time must be timezone-aware")
        consumed = (
            select(func.coalesce(func.sum(CreditLotConsumptionModel.amount), 0))
            .join(
                CreditTransactionModel,
                CreditTransactionModel.id == CreditLotConsumptionModel.transaction_id,
            )
            .where(
                CreditLotConsumptionModel.lot_id == CreditLotModel.id,
                CreditTransactionModel.effective_at <= now,
            )
            .correlate(CreditLotModel)
            .scalar_subquery()
        )
        held = (
            select(func.coalesce(func.sum(CreditReservationAllocationModel.amount), 0))
            .join(
                InferenceCreditReservationModel,
                InferenceCreditReservationModel.id
                == CreditReservationAllocationModel.reservation_id,
            )
            .where(
                CreditReservationAllocationModel.lot_id == CreditLotModel.id,
                InferenceCreditReservationModel.created_at <= now,
                or_(
                    InferenceCreditReservationModel.finalized_at.is_(None),
                    InferenceCreditReservationModel.finalized_at > now,
                ),
            )
            .correlate(CreditLotModel)
            .scalar_subquery()
        )
        available = CreditLotModel.original_amount - consumed - held
        candidates = (
            await self._session.scalars(
                select(CreditLotModel)
                .where(
                    CreditLotModel.expires_at <= now,
                    available > 0,
                )
                .order_by(CreditLotModel.expires_at, CreditLotModel.id)
                .limit(limit)
            )
        ).all()
        if not candidates:
            return 0
        # Wallets are the common serialization boundary for reserve, settle,
        # and expiry. Locking them before lots keeps every path in one order.
        account_ids = sorted({lot.owner_account_id for lot in candidates})
        locked_accounts = (
            await self._session.scalars(
                select(CreditAccountModel)
                .where(CreditAccountModel.id.in_(account_ids))
                .order_by(CreditAccountModel.id)
                .with_for_update()
            )
        ).all()
        if len(locked_accounts) != len(account_ids):
            raise RuntimeError("credit lot owner account is missing")
        lots = (
            await self._session.scalars(
                select(CreditLotModel)
                .where(CreditLotModel.id.in_([lot.id for lot in candidates]))
                .order_by(CreditLotModel.expires_at, CreditLotModel.id)
                .with_for_update(skip_locked=True)
            )
        ).all()
        expired_count = 0
        for lot in lots:
            available = await self._lot_available(lot, now)
            if available <= 0:
                continue
            transaction = self._append_transaction(
                CreditTransactionKind.EXPIRE,
                key_hash=self._hash_key(f"credit-expire:{lot.id}"),
                reference_type="credit_lot",
                reference_id=lot.id,
                postings={lot.owner_account_id: -available, EXPIRED_ACCOUNT_ID: available},
                effective_at=now,
            )
            await self._session.flush()
            self._session.add(
                CreditLotConsumptionModel(
                    lot_id=lot.id,
                    transaction_id=transaction.id,
                    kind=CreditConsumptionKind.EXPIRE.value,
                    amount=available,
                )
            )
            expired_count += 1
        await self._session.flush()
        return expired_count

    async def transaction_page(
        self,
        user_id: UUID,
        *,
        limit: int,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> CreditTransactionPage:
        account = await self._user_account(user_id)
        if account is None:
            return CreditTransactionPage((), None)
        posting_transactions = select(CreditPostingModel.transaction_id).where(
            CreditPostingModel.account_id == account.id
        )
        reservation_transactions = union(
            select(InferenceCreditReservationModel.reserve_transaction_id).where(
                InferenceCreditReservationModel.owner_account_id == account.id
            ),
            select(InferenceCreditReservationModel.final_transaction_id).where(
                InferenceCreditReservationModel.owner_account_id == account.id,
                InferenceCreditReservationModel.final_transaction_id.is_not(None),
            ),
        )
        related_ids = union(posting_transactions, reservation_transactions).subquery()
        statement: Select[tuple[CreditTransactionModel]] = (
            select(CreditTransactionModel)
            .where(CreditTransactionModel.id.in_(select(related_ids.c.transaction_id)))
            .order_by(
                CreditTransactionModel.created_at.desc(),
                CreditTransactionModel.id.desc(),
            )
            .limit(limit + 1)
        )
        if cursor is not None:
            statement = statement.where(
                tuple_(CreditTransactionModel.created_at, CreditTransactionModel.id)
                < cursor
            )
        transactions = list((await self._session.scalars(statement)).all())
        has_more = len(transactions) > limit
        transactions = transactions[:limit]
        if not transactions:
            return CreditTransactionPage((), None)
        ids = [transaction.id for transaction in transactions]
        user_postings = {
            posting.transaction_id: posting.amount
            for posting in (
                await self._session.scalars(
                    select(CreditPostingModel).where(
                        CreditPostingModel.transaction_id.in_(ids),
                        CreditPostingModel.account_id == account.id,
                    )
                )
            ).all()
        }
        reservations = (
            await self._session.scalars(
                select(InferenceCreditReservationModel).where(
                    InferenceCreditReservationModel.owner_account_id == account.id,
                    or_(
                        InferenceCreditReservationModel.reserve_transaction_id.in_(ids),
                        InferenceCreditReservationModel.final_transaction_id.in_(ids),
                    ),
                )
            )
        ).all()
        reserved_deltas: dict[UUID, int] = {}
        for reservation in reservations:
            reserved_deltas[reservation.reserve_transaction_id] = reservation.reserved_amount
            if reservation.final_transaction_id is not None:
                reserved_deltas[reservation.final_transaction_id] = -reservation.reserved_amount
        lots = {
            lot.issuance_transaction_id: lot
            for lot in (
                await self._session.scalars(
                    select(CreditLotModel).where(
                        CreditLotModel.issuance_transaction_id.in_(ids)
                    )
                )
            ).all()
        }
        items = tuple(
            CreditTransaction(
                id=transaction.id,
                kind=CreditTransactionKind(transaction.kind),
                available_delta=user_postings.get(transaction.id, 0),
                reserved_delta=reserved_deltas.get(transaction.id, 0),
                source_kind=(
                    CreditSourceKind(lots[transaction.id].source_kind)
                    if transaction.id in lots
                    else None
                ),
                expires_at=(
                    lots[transaction.id].expires_at
                    if transaction.id in lots
                    else None
                ),
                created_at=transaction.created_at,
            )
            for transaction in transactions
        )
        next_cursor = None
        if has_more:
            last = transactions[-1]
            raw_cursor = f"{last.created_at.isoformat()}|{last.id}".encode()
            next_cursor = base64.urlsafe_b64encode(raw_cursor).decode("ascii").rstrip("=")
        return CreditTransactionPage(items, next_cursor)

    async def _allocate_lots(
        self, account_id: UUID, amount: int, now: datetime
    ) -> list[tuple[UUID, int]]:
        consumed = (
            select(
                CreditLotConsumptionModel.lot_id,
                func.sum(CreditLotConsumptionModel.amount).label("amount"),
            )
            .join(
                CreditTransactionModel,
                CreditTransactionModel.id == CreditLotConsumptionModel.transaction_id,
            )
            .where(CreditTransactionModel.effective_at <= now)
            .group_by(CreditLotConsumptionModel.lot_id)
            .subquery()
        )
        held = (
            select(
                CreditReservationAllocationModel.lot_id,
                func.sum(CreditReservationAllocationModel.amount).label("amount"),
            )
            .join(
                InferenceCreditReservationModel,
                InferenceCreditReservationModel.id
                == CreditReservationAllocationModel.reservation_id,
            )
            .where(
                InferenceCreditReservationModel.created_at <= now,
                or_(
                    InferenceCreditReservationModel.finalized_at.is_(None),
                    InferenceCreditReservationModel.finalized_at > now,
                ),
            )
            .group_by(CreditReservationAllocationModel.lot_id)
            .subquery()
        )
        rows = (
            await self._session.execute(
                select(
                    CreditLotModel,
                    (
                        CreditLotModel.original_amount
                        - func.coalesce(consumed.c.amount, 0)
                        - func.coalesce(held.c.amount, 0)
                    ).label("available"),
                )
                .outerjoin(consumed, consumed.c.lot_id == CreditLotModel.id)
                .outerjoin(held, held.c.lot_id == CreditLotModel.id)
                .where(
                    CreditLotModel.owner_account_id == account_id,
                    CreditLotModel.issued_at <= now,
                    or_(
                        CreditLotModel.expires_at.is_(None),
                        CreditLotModel.expires_at > now,
                    ),
                )
                .order_by(
                    CreditLotModel.expires_at.asc().nullslast(),
                    CreditLotModel.issued_at,
                    CreditLotModel.id,
                )
                .with_for_update(of=CreditLotModel)
            )
        ).all()
        remaining = amount
        allocations: list[tuple[UUID, int]] = []
        for lot, available in rows:
            allocated = min(remaining, int(available))
            if allocated <= 0:
                continue
            allocations.append((lot.id, allocated))
            remaining -= allocated
            if remaining == 0:
                break
        if remaining:
            raise InsufficientCreditsError
        return allocations

    async def _replay_grant(
        self,
        transaction: CreditTransactionModel,
        *,
        user_id: UUID,
        amount: int,
        source_kind: CreditSourceKind,
        expires_at: datetime | None,
    ) -> CreditGrant:
        lot = await self._session.scalar(
            select(CreditLotModel).where(
                CreditLotModel.issuance_transaction_id == transaction.id
            )
        )
        if lot is None:
            raise CreditIdempotencyConflictError
        account = await self._session.get(CreditAccountModel, lot.owner_account_id)
        if (
            transaction.kind != CreditTransactionKind.GRANT.value
            or account is None
            or account.owner_user_id != user_id
            or lot.original_amount != amount
            or lot.source_kind != source_kind.value
            or lot.expires_at != expires_at
        ):
            raise CreditIdempotencyConflictError
        return CreditGrant(transaction.id, lot.id, amount, replayed=True)

    async def _validate_reservation(
        self,
        reservation: InferenceCreditReservationModel,
        user_id: UUID,
        amount: int,
    ) -> InferenceCreditReservationModel:
        owner = await self._session.get(
            CreditAccountModel,
            reservation.owner_account_id,
        )
        if (
            reservation.reserved_amount != amount
            or owner is None
            or owner.owner_user_id != user_id
        ):
            raise CreditIdempotencyConflictError
        return reservation

    async def _lot_available(self, lot: CreditLotModel, now: datetime) -> int:
        consumed, held = await self._lot_usage(lot, now)
        return lot.original_amount - consumed - held

    async def _lot_usage(self, lot: CreditLotModel, now: datetime) -> tuple[int, int]:
        consumed = await self._session.scalar(
            select(func.coalesce(func.sum(CreditLotConsumptionModel.amount), 0))
            .join(
                CreditTransactionModel,
                CreditTransactionModel.id == CreditLotConsumptionModel.transaction_id,
            )
            .where(
                CreditLotConsumptionModel.lot_id == lot.id,
                CreditTransactionModel.effective_at <= now,
            )
        )
        held = await self._session.scalar(
            select(func.coalesce(func.sum(CreditReservationAllocationModel.amount), 0))
            .join(
                InferenceCreditReservationModel,
                InferenceCreditReservationModel.id
                == CreditReservationAllocationModel.reservation_id,
            )
            .where(
                CreditReservationAllocationModel.lot_id == lot.id,
                InferenceCreditReservationModel.created_at <= now,
                or_(
                    InferenceCreditReservationModel.finalized_at.is_(None),
                    InferenceCreditReservationModel.finalized_at > now,
                ),
            )
        )
        return int(consumed or 0), int(held or 0)

    async def _ensure_locked_user_account(self, user_id: UUID) -> CreditAccountModel:
        await self._session.execute(
            pg_insert(CreditAccountModel)
            .values(
                id=uuid4(),
                kind=CreditAccountKind.USER.value,
                owner_user_id=user_id,
                asset_code=CREDIT_ASSET_CODE,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    CreditAccountModel.owner_user_id,
                    CreditAccountModel.asset_code,
                ],
                index_where=CreditAccountModel.owner_user_id.is_not(None),
            )
        )
        account = await self._locked_user_account(user_id)
        if account is None:
            raise RuntimeError("failed to create credit account")
        return account

    async def _locked_user_account(self, user_id: UUID) -> CreditAccountModel | None:
        return await self._session.scalar(
            self._user_account_statement(user_id).with_for_update()
        )

    async def _user_account(self, user_id: UUID) -> CreditAccountModel | None:
        return await self._session.scalar(self._user_account_statement(user_id))

    @staticmethod
    def _user_account_statement(user_id: UUID) -> Select[tuple[CreditAccountModel]]:
        return select(CreditAccountModel).where(
            CreditAccountModel.owner_user_id == user_id,
            CreditAccountModel.asset_code == CREDIT_ASSET_CODE,
        )

    async def _spendable_balance(self, account_id: UUID, now: datetime) -> int:
        consumed = (
            select(func.coalesce(func.sum(CreditLotConsumptionModel.amount), 0))
            .join(
                CreditTransactionModel,
                CreditTransactionModel.id == CreditLotConsumptionModel.transaction_id,
            )
            .where(
                CreditLotConsumptionModel.lot_id == CreditLotModel.id,
                CreditTransactionModel.effective_at <= now,
            )
            .correlate(CreditLotModel)
            .scalar_subquery()
        )
        held = (
            select(func.coalesce(func.sum(CreditReservationAllocationModel.amount), 0))
            .join(
                InferenceCreditReservationModel,
                InferenceCreditReservationModel.id
                == CreditReservationAllocationModel.reservation_id,
            )
            .where(
                CreditReservationAllocationModel.lot_id == CreditLotModel.id,
                InferenceCreditReservationModel.created_at <= now,
                or_(
                    InferenceCreditReservationModel.finalized_at.is_(None),
                    InferenceCreditReservationModel.finalized_at > now,
                ),
            )
            .correlate(CreditLotModel)
            .scalar_subquery()
        )
        value = await self._session.scalar(
            select(
                func.coalesce(
                    func.sum(CreditLotModel.original_amount - consumed - held),
                    0,
                )
            ).where(
                CreditLotModel.owner_account_id == account_id,
                CreditLotModel.issued_at <= now,
                or_(CreditLotModel.expires_at.is_(None), CreditLotModel.expires_at > now),
            )
        )
        return int(value or 0)

    def _append_transaction(
        self,
        kind: CreditTransactionKind,
        *,
        key_hash: str,
        reference_type: str,
        reference_id: UUID | None,
        postings: Mapping[UUID, int],
        effective_at: datetime,
    ) -> CreditTransactionModel:
        normalized = {account_id: amount for account_id, amount in postings.items() if amount}
        if len(normalized) < 2 or sum(normalized.values()) != 0:
            raise ValueError("credit transaction must contain balanced postings")
        transaction = CreditTransactionModel(
            id=uuid4(),
            kind=kind.value,
            idempotency_key_hash=key_hash,
            reference_type=reference_type,
            reference_id=reference_id,
            effective_at=effective_at,
        )
        self._session.add(transaction)
        for account_id, amount in normalized.items():
            self._session.add(
                CreditPostingModel(
                    transaction_id=transaction.id,
                    account_id=account_id,
                    amount=amount,
                )
            )
        return transaction

    @staticmethod
    def _hash_key(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _advisory_key(key_hash: str) -> int:
        return int.from_bytes(bytes.fromhex(key_hash[:16]), "big", signed=True)
