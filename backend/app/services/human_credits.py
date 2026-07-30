from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.answerers import (
    AnswererId,
    RuntimeKind,
    get_answerer,
    get_human_credit_terms,
)
from app.domain.credits import FREE_CREDIT_ALLOWANCE_POLICY, FreeCreditAllowancePolicy
from app.domain.reasoning import ReasoningEffort
from app.domain.responses import Execution, ResponseStatus
from app.models.credits import InferenceCreditReservationModel
from app.models.humans import HumanClaimModel, HumanTaskModel
from app.models.platform import ExecutionModel, ResponseRequestModel
from app.repositories.credits import CreditLedgerRepository
from app.services.credit_allowance import FreeCreditAllowanceService


class HumanCreditService:
    """Connects Human request lifecycle facts to the shared credit ledger."""

    def __init__(
        self,
        session: AsyncSession,
        allowance_policy: FreeCreditAllowancePolicy = FREE_CREDIT_ALLOWANCE_POLICY,
    ) -> None:
        self._session = session
        self._ledger = CreditLedgerRepository(session)
        self._allowance = FreeCreditAllowanceService(session, allowance_policy)

    async def reserve(
        self,
        user_id: UUID,
        execution: Execution,
        answerer_id: AnswererId,
        reasoning_effort: ReasoningEffort,
    ) -> None:
        terms = get_human_credit_terms(answerer_id, reasoning_effort)
        _, now = await self._allowance.start_for_request(user_id, execution.id)
        await self._ledger.reserve_inference(
            user_id,
            execution.id,
            terms.customer_charge,
            now=now,
        )

    async def settle_answer(self, execution_id: UUID, performer_user_id: UUID) -> None:
        reservation = await self._session.scalar(
            select(InferenceCreditReservationModel).where(
                InferenceCreditReservationModel.execution_reference_id == execution_id
            )
        )
        # Requests already waiting when this feature is deployed have no financial
        # reservation. They remain free instead of inventing a retroactive charge.
        if reservation is None:
            return

        row = (
            await self._session.execute(
                select(ExecutionModel, ResponseRequestModel, HumanClaimModel)
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .join(
                    HumanTaskModel,
                    HumanTaskModel.execution_id == ExecutionModel.id,
                )
                .join(
                    HumanClaimModel,
                    HumanClaimModel.execution_id == ExecutionModel.id,
                )
                .where(
                    ExecutionModel.id == execution_id,
                    HumanClaimModel.performer_user_id == performer_user_id,
                    HumanClaimModel.status == "answered",
                )
                .with_for_update(of=ExecutionModel)
            )
        ).one_or_none()
        if row is None:
            raise RuntimeError("completed Human answer is missing")
        execution, request, _ = row
        if execution.status != ResponseStatus.COMPLETED.value:
            raise RuntimeError("Human reward cannot be settled before completion")

        answerer_id = AnswererId(request.requested_answerer)
        answerer = get_answerer(answerer_id)
        if answerer is None or answerer.runtime_kind is not RuntimeKind.HUMAN:
            raise RuntimeError("Human reward references a non-Human answerer")
        terms = get_human_credit_terms(
            answerer_id,
            ReasoningEffort(request.reasoning_effort),
        )
        await self._ledger.finalize_human(
            execution_id,
            terms.customer_charge,
            reward_user_id=performer_user_id,
            reward_amount=terms.performer_reward,
        )

    async def release(self, execution_id: UUID) -> None:
        await self._ledger.finalize_inference(execution_id, 0)
