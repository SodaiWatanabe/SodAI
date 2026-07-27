from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.credits import (
    CREDIT_ASSET_CODE,
    FREE_CREDIT_ALLOWANCE_POLICY,
    BillingOutcome,
    BillingReason,
    CreditIdempotencyConflictError,
    FreeCreditAllowancePolicy,
    InferenceTariff,
)
from app.domain.principals import Principal, PrincipalKind
from app.domain.responses import Execution, ResponseStatus
from app.models.credits import InferenceBillingIntentModel, InferenceUsageRecordModel
from app.models.platform import ExecutionModel
from app.repositories.credits import CreditLedgerRepository
from app.services.credit_allowance import FreeCreditAllowanceService


class InferenceBillingService:
    """Coordinates inference lifecycle facts with the append-only credit ledger."""

    def __init__(
        self,
        session: AsyncSession,
        allowance_policy: FreeCreditAllowancePolicy | None = FREE_CREDIT_ALLOWANCE_POLICY,
    ) -> None:
        self._session = session
        self._ledger = CreditLedgerRepository(session)
        self._allowance = (
            FreeCreditAllowanceService(session, allowance_policy)
            if allowance_policy is not None
            else None
        )

    async def register(
        self,
        principal: Principal,
        execution: Execution,
        tariff: InferenceTariff,
    ) -> None:
        existing = await self._session.get(InferenceBillingIntentModel, execution.id)
        user_id = principal.id if principal.kind is PrincipalKind.USER else None
        if existing is not None:
            if not self._matches(existing, user_id, tariff):
                raise CreditIdempotencyConflictError
            return
        if not tariff.is_free and user_id is None:
            raise CreditIdempotencyConflictError("paid inference cannot be reserved by a guest")
        self._session.add(
            InferenceBillingIntentModel(
                execution_reference_id=execution.id,
                user_id=user_id,
                asset_code=CREDIT_ASSET_CODE,
                tariff_revision=tariff.revision,
                fixed_charge=tariff.fixed_charge,
                input_token_rate=tariff.input_token_rate,
                output_token_rate=tariff.output_token_rate,
                maximum_charge=tariff.maximum_charge,
                unmetered_charge=tariff.unmetered_charge,
            )
        )
        await self._session.flush()
        if user_id is not None and not tariff.is_free:
            now: datetime | None = None
            if self._allowance is not None:
                _, now = await self._allowance.start_for_request(
                    user_id,
                    execution.id,
                )
            await self._ledger.reserve_inference(
                user_id,
                execution.id,
                tariff.maximum_charge,
                now=now,
            )

    async def finalize(self, execution_id: UUID) -> InferenceUsageRecordModel:
        existing = await self._session.get(InferenceUsageRecordModel, execution_id)
        if existing is not None:
            return existing
        row = (
            await self._session.execute(
                select(ExecutionModel, InferenceBillingIntentModel)
                .join(
                    InferenceBillingIntentModel,
                    InferenceBillingIntentModel.execution_reference_id == ExecutionModel.id,
                )
                .where(ExecutionModel.id == execution_id)
                .with_for_update(of=ExecutionModel)
            )
        ).one_or_none()
        if row is None:
            raise RuntimeError("inference billing intent is missing")
        execution, intent = row
        # The Execution lock serializes terminal billing. A competing projector
        # may have committed usage while this transaction waited for the lock.
        existing = await self._session.get(InferenceUsageRecordModel, execution_id)
        if existing is not None:
            return existing
        if execution.status not in {
            ResponseStatus.COMPLETED.value,
            ResponseStatus.FAILED.value,
            ResponseStatus.CANCELLED.value,
        }:
            raise RuntimeError("inference usage cannot be finalized before execution")

        tariff = InferenceTariff(
            revision=intent.tariff_revision,
            fixed_charge=intent.fixed_charge,
            input_token_rate=intent.input_token_rate,
            output_token_rate=intent.output_token_rate,
            maximum_charge=intent.maximum_charge,
            unmetered_charge=intent.unmetered_charge,
        )
        outcome = BillingOutcome(execution.status)
        if outcome is BillingOutcome.FAILED:
            charge = 0
            reason = BillingReason.FAILED
        elif outcome is BillingOutcome.CANCELLED:
            if execution.input_tokens is None:
                charge = 0
            else:
                charge = tariff.charge(
                    execution.input_tokens,
                    execution.output_tokens or 0,
                )
            reason = BillingReason.CANCELLED
        elif tariff.is_free:
            charge = 0
            reason = BillingReason.FREE
        elif execution.input_tokens is None or execution.output_tokens is None:
            charge = tariff.unmetered_charge
            reason = BillingReason.UNMETERED
        else:
            charge = tariff.charge(execution.input_tokens, execution.output_tokens)
            reason = BillingReason.COMPLETED

        await self._ledger.finalize_inference(execution.id, charge)
        usage = InferenceUsageRecordModel(
            execution_reference_id=execution.id,
            user_id=intent.user_id,
            outcome=outcome.value,
            input_tokens=execution.input_tokens,
            output_tokens=execution.output_tokens,
            tariff_revision=tariff.revision,
            charged_amount=charge,
            billing_reason=reason.value,
            finalized_at=datetime.now(timezone.utc),
        )
        self._session.add(usage)
        await self._session.flush()
        return usage

    @staticmethod
    def _matches(
        intent: InferenceBillingIntentModel,
        user_id: UUID | None,
        tariff: InferenceTariff,
    ) -> bool:
        return (
            intent.user_id == user_id
            and intent.asset_code == CREDIT_ASSET_CODE
            and intent.tariff_revision == tariff.revision
            and intent.fixed_charge == tariff.fixed_charge
            and intent.input_token_rate == tariff.input_token_rate
            and intent.output_token_rate == tariff.output_token_rate
            and intent.maximum_charge == tariff.maximum_charge
            and intent.unmetered_charge == tariff.unmetered_charge
        )
