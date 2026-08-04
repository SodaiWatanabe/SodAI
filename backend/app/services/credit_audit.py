from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.answerers import AnswererId, get_human_credit_terms
from app.domain.credits import (
    REVENUE_ACCOUNT_ID,
    CreditReservationStatus,
    CreditSourceKind,
    HumanCreditTerms,
    earned_credit_expiration,
)
from app.domain.reasoning import ReasoningEffort
from app.domain.responses import ResponseStatus
from app.models.credits import (
    CreditAccountModel,
    CreditLotModel,
    CreditPostingModel,
    InferenceCreditReservationModel,
)
from app.models.humans import HumanClaimModel, HumanTaskModel
from app.models.platform import (
    ExecutionModel,
    ResponseRequestModel,
    SpaceModel,
    ThreadModel,
)


@dataclass(frozen=True, slots=True)
class CreditAuditReport:
    scanned_earned_lots: int
    scanned_human_reservations: int
    issues: tuple[str, ...]


class CreditAuditService:
    """Read-only cross-domain checks kept outside the ledger write path."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def audit(self) -> CreditAuditReport:
        async with self._session_factory() as session:
            earned_lots = list(
                (
                    await session.scalars(
                        select(CreditLotModel)
                        .where(
                            CreditLotModel.source_kind
                            == CreditSourceKind.EARNED.value
                        )
                        .order_by(CreditLotModel.issued_at, CreditLotModel.id)
                    )
                ).all()
            )
            rows = (
                await session.execute(
                    select(
                        InferenceCreditReservationModel,
                        CreditAccountModel.owner_user_id,
                        ExecutionModel.status,
                        ResponseRequestModel.requested_answerer,
                        ResponseRequestModel.reasoning_effort,
                        SpaceModel.owner_user_id,
                    )
                    .join(
                        ExecutionModel,
                        ExecutionModel.id
                        == InferenceCreditReservationModel.execution_reference_id,
                    )
                    .join(
                        HumanTaskModel,
                        HumanTaskModel.execution_id == ExecutionModel.id,
                    )
                    .join(
                        ResponseRequestModel,
                        ResponseRequestModel.id
                        == ExecutionModel.response_request_id,
                    )
                    .join(ThreadModel, ThreadModel.id == ExecutionModel.thread_id)
                    .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
                    .join(
                        CreditAccountModel,
                        CreditAccountModel.id
                        == InferenceCreditReservationModel.owner_account_id,
                    )
                    .order_by(InferenceCreditReservationModel.created_at)
                )
            ).all()
            issues: list[str] = []
            for lot in earned_lots:
                if lot.expires_at != earned_credit_expiration(lot.issued_at):
                    issues.append(
                        f"earned_lot={lot.id}: expiration differs from application policy"
                    )
            for (
                reservation,
                reservation_owner_user_id,
                execution_status,
                requested_answerer,
                reasoning_effort,
                requester_user_id,
            ) in rows:
                prefix = f"execution={reservation.execution_reference_id}"
                try:
                    get_human_credit_terms(
                        AnswererId(requested_answerer),
                        ReasoningEffort(reasoning_effort),
                    )
                except ValueError:
                    issues.append(f"{prefix}: unknown Human credit terms")
                    continue
                if reservation_owner_user_id != requester_user_id:
                    issues.append(f"{prefix}: reservation owner differs from requester")

                if reservation.status == CreditReservationStatus.HELD.value:
                    if execution_status in {
                        ResponseStatus.COMPLETED.value,
                        ResponseStatus.FAILED.value,
                        ResponseStatus.CANCELLED.value,
                    }:
                        issues.append(f"{prefix}: terminal execution still has a held reserve")
                    continue
                if reservation.status == CreditReservationStatus.RELEASED.value:
                    if reservation.settled_amount != 0:
                        issues.append(f"{prefix}: released reservation has a charge")
                    continue
                if reservation.status != CreditReservationStatus.SETTLED.value:
                    issues.append(f"{prefix}: unknown reservation status")
                    continue
                if execution_status != ResponseStatus.COMPLETED.value:
                    issues.append(f"{prefix}: reward settled before Human completion")
                if reservation.final_transaction_id is None:
                    issues.append(f"{prefix}: settled reservation has no transaction")
                    continue
                try:
                    settled_terms = HumanCreditTerms.from_customer_charge(
                        reservation.settled_amount
                    )
                except ValueError:
                    issues.append(f"{prefix}: settled charge cannot split at 10 percent")
                    continue

                await self._audit_reward(
                    session,
                    reservation.execution_reference_id,
                    reservation.final_transaction_id,
                    settled_terms.performer_reward,
                    settled_terms.platform_revenue,
                    issues,
                )
            return CreditAuditReport(len(earned_lots), len(rows), tuple(issues))

    @staticmethod
    async def _audit_reward(
        session: AsyncSession,
        execution_id: UUID,
        transaction_id: UUID,
        expected_reward: int,
        expected_revenue: int,
        issues: list[str],
    ) -> None:
        prefix = f"execution={execution_id}"
        performer_ids = list(
            (
                await session.scalars(
                    select(HumanClaimModel.performer_user_id).where(
                        HumanClaimModel.execution_id == execution_id,
                        HumanClaimModel.status == "answered",
                    )
                )
            ).all()
        )
        if len(performer_ids) != 1:
            issues.append(f"{prefix}: settled reward lacks one answered claim")
            return
        performer_user_id = performer_ids[0]
        reward_lot = await session.scalar(
            select(CreditLotModel).where(
                CreditLotModel.issuance_transaction_id == transaction_id
            )
        )
        if reward_lot is None:
            issues.append(f"{prefix}: earned reward lot is missing")
            return
        reward_owner_id = await session.scalar(
            select(CreditAccountModel.owner_user_id).where(
                CreditAccountModel.id == reward_lot.owner_account_id
            )
        )
        if (
            reward_owner_id != performer_user_id
            or reward_lot.source_kind != CreditSourceKind.EARNED.value
            or reward_lot.original_amount != expected_reward
            or reward_lot.expires_at
            != earned_credit_expiration(reward_lot.issued_at)
        ):
            issues.append(f"{prefix}: earned reward lot differs from application policy")
        reward_posting = await session.scalar(
            select(func.coalesce(func.sum(CreditPostingModel.amount), 0)).where(
                CreditPostingModel.transaction_id == transaction_id,
                CreditPostingModel.account_id == reward_lot.owner_account_id,
            )
        )
        revenue_posting = await session.scalar(
            select(func.coalesce(func.sum(CreditPostingModel.amount), 0)).where(
                CreditPostingModel.transaction_id == transaction_id,
                CreditPostingModel.account_id == REVENUE_ACCOUNT_ID,
            )
        )
        if int(reward_posting or 0) != expected_reward:
            issues.append(f"{prefix}: reward posting differs from application policy")
        if int(revenue_posting or 0) != expected_revenue:
            issues.append(f"{prefix}: platform posting differs from 10 percent")
