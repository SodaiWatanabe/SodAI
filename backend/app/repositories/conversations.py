from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.conversations import (
    Conversation,
    ConversationCreation,
    ConversationPrincipal,
    ConversationSummary,
    InferenceRun,
    Message,
    MessageStatus,
    PrincipalKind,
    RunStatus,
    Speaker,
)
from app.domain.model_catalog import ModelId
from app.models.conversation import ConversationModel, InferenceRunModel, MessageModel


class ConversationNotFoundError(Exception):
    pass


class ConversationBusyError(Exception):
    pass


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        principal: ConversationPrincipal,
        content: str,
        model: ModelId,
        resolved_model: str,
    ) -> ConversationCreation:
        now = datetime.now(timezone.utc)
        conversation = ConversationModel(
            title=_title_from(content),
            default_model=model.value,
            status="active",
            last_activity_at=now,
            owner_user_id=principal.id if principal.kind is PrincipalKind.USER else None,
            guest_session_id=principal.id if principal.kind is PrincipalKind.GUEST else None,
        )
        input_message = MessageModel(
            conversation=conversation,
            speaker=Speaker.PARTNER.value,
            content=content,
            status=MessageStatus.COMPLETED.value,
            ordinal=0,
        )
        output_message = MessageModel(
            conversation=conversation,
            speaker=Speaker.SODAI.value,
            content="",
            status=MessageStatus.STREAMING.value,
            ordinal=1,
        )
        self._session.add_all([conversation, input_message, output_message])
        await self._session.flush()
        run = InferenceRunModel(
            conversation_id=conversation.id,
            input_message_id=input_message.id,
            output_message_id=output_message.id,
            requested_model=model.value,
            resolved_model=resolved_model,
            status=RunStatus.QUEUED.value,
            partial_output="",
        )
        self._session.add(run)
        await self._session.flush()
        return ConversationCreation(
            conversation=self._to_conversation(conversation, [input_message, output_message], run),
            run=self._to_run(run),
        )

    async def list(
        self, principal: ConversationPrincipal, *, limit: int = 50
    ) -> list[ConversationSummary]:
        statement = (
            select(ConversationModel)
            .where(self._owned_by(principal), ConversationModel.status == "active")
            .order_by(ConversationModel.last_activity_at.desc())
            .limit(limit)
        )
        rows = (await self._session.scalars(statement)).all()
        return [self._to_summary(row) for row in rows]

    async def get(self, principal: ConversationPrincipal, conversation_id: UUID) -> Conversation:
        statement = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id, self._owned_by(principal))
            .options(
                selectinload(ConversationModel.messages),
                selectinload(ConversationModel.runs),
            )
        )
        conversation = await self._session.scalar(statement)
        if conversation is None:
            raise ConversationNotFoundError
        active_run_model = next(
            (
                run
                for run in reversed(conversation.runs)
                if run.status in {RunStatus.QUEUED.value, RunStatus.RUNNING.value}
            ),
            None,
        )
        return self._to_conversation(conversation, conversation.messages, active_run_model)

    async def append_turn(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        content: str,
        model: ModelId,
        resolved_model: str,
    ) -> ConversationCreation:
        conversation = await self._locked_conversation(principal, conversation_id)
        active_statement = select(InferenceRunModel.id).where(
            InferenceRunModel.conversation_id == conversation_id,
            InferenceRunModel.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
        )
        if await self._session.scalar(active_statement) is not None:
            raise ConversationBusyError

        last_ordinal = await self._session.scalar(
            select(func.max(MessageModel.ordinal)).where(
                MessageModel.conversation_id == conversation_id
            )
        )
        input_message = MessageModel(
            conversation_id=conversation_id,
            speaker=Speaker.PARTNER.value,
            content=content,
            status=MessageStatus.COMPLETED.value,
            ordinal=(last_ordinal or 0) + 1,
        )
        output_message = MessageModel(
            conversation_id=conversation_id,
            speaker=Speaker.SODAI.value,
            content="",
            status=MessageStatus.STREAMING.value,
            ordinal=(last_ordinal or 0) + 2,
        )
        now = datetime.now(timezone.utc)
        conversation.default_model = model.value
        conversation.last_activity_at = now
        self._session.add_all([input_message, output_message])
        await self._session.flush()
        run = InferenceRunModel(
            conversation_id=conversation_id,
            input_message_id=input_message.id,
            output_message_id=output_message.id,
            requested_model=model.value,
            resolved_model=resolved_model,
            status=RunStatus.QUEUED.value,
            partial_output="",
        )
        self._session.add(run)
        await self._session.flush()
        return ConversationCreation(
            conversation=self._to_conversation(conversation, [input_message, output_message], run),
            run=self._to_run(run),
        )

    async def begin_run(self, run_id: UUID) -> tuple[InferenceRunModel, MessageModel]:
        run = await self._session.get(InferenceRunModel, run_id)
        if run is None:
            raise ConversationNotFoundError
        output = await self._session.get(MessageModel, run.output_message_id)
        if output is None:
            raise ConversationNotFoundError
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(timezone.utc)
        await self._session.flush()
        return run, output

    async def save_delta(self, run_id: UUID, content: str) -> None:
        run = await self._session.get(InferenceRunModel, run_id)
        if run is None:
            raise ConversationNotFoundError
        output = await self._session.get(MessageModel, run.output_message_id)
        if output is None:
            raise ConversationNotFoundError
        run.partial_output = content
        output.content = content
        await self._session.flush()

    async def complete_run(self, run_id: UUID, content: str) -> None:
        run = await self._session.get(InferenceRunModel, run_id)
        if run is None:
            raise ConversationNotFoundError
        output = await self._session.get(MessageModel, run.output_message_id)
        conversation = await self._session.get(ConversationModel, run.conversation_id)
        if output is None or conversation is None:
            raise ConversationNotFoundError
        now = datetime.now(timezone.utc)
        run.partial_output = content
        run.status = RunStatus.COMPLETED.value
        run.finished_at = now
        output.content = content
        output.status = MessageStatus.COMPLETED.value
        conversation.last_activity_at = now
        await self._session.flush()

    async def fail_run(self, run_id: UUID) -> None:
        run = await self._session.get(InferenceRunModel, run_id)
        if run is None:
            return
        output = await self._session.get(MessageModel, run.output_message_id)
        run.status = RunStatus.FAILED.value
        run.error_code = "pseudo_generation_failed"
        run.finished_at = datetime.now(timezone.utc)
        if output is not None:
            output.status = MessageStatus.FAILED.value
        await self._session.flush()

    async def fail_interrupted_runs(self) -> int:
        now = datetime.now(timezone.utc)
        output_ids = list(
            await self._session.scalars(
                update(InferenceRunModel)
                .where(
                    InferenceRunModel.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value])
                )
                .values(
                    status=RunStatus.FAILED.value,
                    error_code="worker_interrupted",
                    finished_at=now,
                )
                .returning(InferenceRunModel.output_message_id)
            )
        )
        if output_ids:
            await self._session.execute(
                update(MessageModel)
                .where(MessageModel.id.in_(output_ids))
                .values(status=MessageStatus.FAILED.value)
            )
        return len(output_ids)

    async def _locked_conversation(
        self, principal: ConversationPrincipal, conversation_id: UUID
    ) -> ConversationModel:
        statement = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id, self._owned_by(principal))
            .with_for_update()
        )
        conversation = await self._session.scalar(statement)
        if conversation is None:
            raise ConversationNotFoundError
        return conversation

    @staticmethod
    def _owned_by(principal: ConversationPrincipal):
        if principal.kind is PrincipalKind.USER:
            return ConversationModel.owner_user_id == principal.id
        return ConversationModel.guest_session_id == principal.id

    @staticmethod
    def _to_summary(model: ConversationModel) -> ConversationSummary:
        return ConversationSummary(
            id=model.id,
            title=model.title,
            model=ModelId(model.default_model),
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_activity_at=model.last_activity_at,
        )

    @classmethod
    def _to_conversation(
        cls,
        model: ConversationModel,
        messages: list[MessageModel],
        active_run: InferenceRunModel | None,
    ) -> Conversation:
        return Conversation(
            id=model.id,
            title=model.title,
            model=ModelId(model.default_model),
            messages=tuple(cls._to_message(message) for message in messages),
            active_run=cls._to_run(active_run) if active_run else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_activity_at=model.last_activity_at,
        )

    @staticmethod
    def _to_message(model: MessageModel) -> Message:
        return Message(
            id=model.id,
            conversation_id=model.conversation_id,
            speaker=Speaker(model.speaker),
            content=model.content,
            status=MessageStatus(model.status),
            ordinal=model.ordinal,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_run(model: InferenceRunModel) -> InferenceRun:
        return InferenceRun(
            id=model.id,
            conversation_id=model.conversation_id,
            input_message_id=model.input_message_id,
            output_message_id=model.output_message_id,
            requested_model=ModelId(model.requested_model),
            resolved_model=model.resolved_model,
            status=RunStatus(model.status),
            created_at=model.created_at,
        )


def _title_from(content: str) -> str:
    compact = " ".join(content.split())
    return compact if len(compact) <= 36 else f"{compact[:35]}…"
