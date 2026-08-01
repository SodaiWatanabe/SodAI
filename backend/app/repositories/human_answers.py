from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.answerers import AnswererId, get_answerer
from app.domain.humans import HumanAnswerDetail, HumanAnswerSummary
from app.domain.reasoning import ReasoningEffort
from app.domain.responses import ResponseStatus
from app.models.humans import HumanClaimModel
from app.models.platform import (
    EntryTextContentModel,
    ExecutionModel,
    ResponseContextItemModel,
    ResponseRequestModel,
)
from app.repositories.humans import load_human_context


class HumanAnswerNotFoundError(Exception):
    pass


class SqlAlchemyHumanAnswerHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def page(
        self,
        user_id: UUID,
        *,
        limit: int,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> tuple[tuple[HumanAnswerSummary, ...], bool]:
        statement = (
            select(
                ExecutionModel.id,
                ResponseRequestModel.requested_answerer,
                ResponseRequestModel.reasoning_effort,
                EntryTextContentModel.content,
                HumanClaimModel.finished_at,
            )
            .select_from(HumanClaimModel)
            .join(ExecutionModel, ExecutionModel.id == HumanClaimModel.execution_id)
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .join(
                ResponseContextItemModel,
                and_(
                    ResponseContextItemModel.response_request_id == ResponseRequestModel.id,
                    ResponseContextItemModel.thread_id == ResponseRequestModel.thread_id,
                    ResponseContextItemModel.entry_id == ResponseRequestModel.input_entry_id,
                ),
            )
            .join(
                EntryTextContentModel,
                EntryTextContentModel.entry_id == ResponseRequestModel.input_entry_id,
            )
            .where(
                HumanClaimModel.performer_user_id == user_id,
                HumanClaimModel.status == "answered",
                ExecutionModel.status == ResponseStatus.COMPLETED.value,
                ExecutionModel.result_entry_id.is_not(None),
                HumanClaimModel.finished_at.is_not(None),
            )
            .order_by(
                HumanClaimModel.finished_at.desc(),
                ExecutionModel.id.desc(),
            )
            .limit(limit + 1)
        )
        if cursor is not None:
            statement = statement.where(
                tuple_(HumanClaimModel.finished_at, ExecutionModel.id) < cursor
            )
        rows = (await self._session.execute(statement)).all()
        has_more = len(rows) > limit
        items = tuple(
            HumanAnswerSummary(
                execution_id=execution_id,
                answerer_name=_answerer_name(requested_answerer),
                reasoning_effort=ReasoningEffort(reasoning_effort),
                prompt_preview=_prompt_preview(prompt),
                answered_at=_answered_at(answered_at),
            )
            for execution_id, requested_answerer, reasoning_effort, prompt, answered_at in rows[
                :limit
            ]
        )
        return items, has_more

    async def get(self, user_id: UUID, execution_id: UUID) -> HumanAnswerDetail:
        answer_text = aliased(EntryTextContentModel)
        row = (
            await self._session.execute(
                select(
                    ResponseRequestModel.id,
                    ResponseRequestModel.requested_answerer,
                    ResponseRequestModel.reasoning_effort,
                    HumanClaimModel.finished_at,
                    answer_text.content,
                )
                .select_from(HumanClaimModel)
                .join(
                    ExecutionModel,
                    ExecutionModel.id == HumanClaimModel.execution_id,
                )
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .join(
                    answer_text,
                    answer_text.entry_id == ExecutionModel.result_entry_id,
                )
                .where(
                    HumanClaimModel.performer_user_id == user_id,
                    HumanClaimModel.execution_id == execution_id,
                    HumanClaimModel.status == "answered",
                    ExecutionModel.status == ResponseStatus.COMPLETED.value,
                    ExecutionModel.result_entry_id.is_not(None),
                    HumanClaimModel.finished_at.is_not(None),
                )
            )
        ).one_or_none()
        if row is None:
            raise HumanAnswerNotFoundError
        request_id, requested_answerer, reasoning_effort, answered_at, answer = row
        return HumanAnswerDetail(
            execution_id=execution_id,
            answerer_name=_answerer_name(requested_answerer),
            reasoning_effort=ReasoningEffort(reasoning_effort),
            answered_at=_answered_at(answered_at),
            context=await load_human_context(self._session, request_id),
            answer=answer,
        )


def _answerer_name(value: str) -> str:
    answerer = get_answerer(AnswererId(value))
    if answerer is None:
        raise RuntimeError("Human answer references an unknown answerer")
    return answerer.name


def _prompt_preview(content: str, limit: int = 120) -> str:
    normalized = " ".join(content.split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit].rstrip()}…"


def _answered_at(value: datetime | None) -> datetime:
    if value is None:
        raise RuntimeError("Answered Human claim is missing its completion time")
    return value
