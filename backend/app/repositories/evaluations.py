from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.principals import Principal, PrincipalKind
from app.domain.responses import (
    ResponseEvaluation,
    ResponseEvaluationValue,
    ResponseStatus,
)
from app.models.platform import (
    ActorModel,
    ExecutionModel,
    ResponseEvaluationModel,
    ResponseRequestModel,
)


class ResponseEvaluationNotFoundError(Exception):
    pass


class ResponseEvaluationNotReadyError(Exception):
    pass


class ResponseEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set(
        self,
        principal: Principal,
        execution_id: UUID,
        value: ResponseEvaluationValue,
    ) -> ResponseEvaluation:
        execution = await self._locked_execution(principal, execution_id)
        evaluation = execution.evaluation
        if evaluation is None:
            evaluation = ResponseEvaluationModel(
                execution_id=execution.id,
                value=value.value,
            )
            execution.evaluation = evaluation
        else:
            evaluation.value = value.value
        await self._session.flush()
        return self._to_domain(evaluation)

    async def clear(self, principal: Principal, execution_id: UUID) -> None:
        execution = await self._locked_execution(principal, execution_id)
        if execution.evaluation is None:
            return
        await self._session.delete(execution.evaluation)
        await self._session.flush()

    async def _locked_execution(
        self,
        principal: Principal,
        execution_id: UUID,
    ) -> ExecutionModel:
        owner_filter = (
            ActorModel.owner_user_id == principal.id
            if principal.kind is PrincipalKind.USER
            else ActorModel.guest_session_id == principal.id
        )
        execution = await self._session.scalar(
            select(ExecutionModel)
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .join(
                ActorModel,
                ActorModel.id == ResponseRequestModel.requester_actor_id,
            )
            .where(
                ExecutionModel.id == execution_id,
                owner_filter,
            )
            .options(selectinload(ExecutionModel.evaluation))
            .with_for_update(of=ExecutionModel)
        )
        if execution is None:
            raise ResponseEvaluationNotFoundError
        if (
            execution.status != ResponseStatus.COMPLETED.value
            or execution.result_entry_id is None
        ):
            raise ResponseEvaluationNotReadyError
        return execution

    @staticmethod
    def _to_domain(model: ResponseEvaluationModel) -> ResponseEvaluation:
        return ResponseEvaluation(
            execution_id=model.execution_id,
            value=ResponseEvaluationValue(model.value),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
