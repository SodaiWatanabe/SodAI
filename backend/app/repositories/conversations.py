from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sodai_contracts.inference import (
    MAX_GENERATION_INPUT_BYTES,
    MAX_GENERATION_TURNS,
    GenerationEvent,
    GenerationEventType,
    GenerationTurn,
    InferenceSpeaker,
)
from sqlalchemy import func, select
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
from app.domain.inference import (
    InferenceEventDisposition,
    InferenceProjection,
    InferenceProjectionResult,
    PendingInferenceOutbox,
    classify_inference_event,
)
from app.domain.model_catalog import ModelId
from app.models.conversation import (
    ConversationModel,
    InferenceOutboxModel,
    InferenceRunModel,
    MessageModel,
)


class ConversationNotFoundError(Exception):
    pass


class ConversationBusyError(Exception):
    pass


INFERENCE_ADMISSION_LOCK_KEY = 0x534F444149


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        principal: ConversationPrincipal,
        content: str,
        model: ModelId,
        resolved_model: str,
        attempt_id: UUID,
        lease_expires_at: datetime,
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
            attempt_id=attempt_id,
            requested_model=model.value,
            resolved_model=resolved_model,
            status=RunStatus.QUEUED.value,
            partial_output="",
            lease_expires_at=lease_expires_at,
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
            .where(
                ConversationModel.id == conversation_id,
                self._owned_by(principal),
                ConversationModel.status == "active",
            )
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

    async def update_title(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        title: str,
    ) -> ConversationSummary:
        conversation = await self._locked_conversation(principal, conversation_id)
        conversation.title = title
        await self._session.flush()
        return self._to_summary(conversation)

    async def archive(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
    ) -> None:
        statement = (
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id, self._owned_by(principal))
            .with_for_update()
        )
        conversation = await self._session.scalar(statement)
        if conversation is None:
            raise ConversationNotFoundError
        if conversation.status == "archived":
            return
        conversation.status = "archived"
        await self._session.flush()

    async def append_turn(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        content: str,
        model: ModelId,
        resolved_model: str,
        attempt_id: UUID,
        lease_expires_at: datetime,
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
            attempt_id=attempt_id,
            requested_model=model.value,
            resolved_model=resolved_model,
            status=RunStatus.QUEUED.value,
            partial_output="",
            lease_expires_at=lease_expires_at,
        )
        self._session.add(run)
        await self._session.flush()
        return ConversationCreation(
            conversation=self._to_conversation(conversation, [input_message, output_message], run),
            run=self._to_run(run),
        )

    async def generation_turns(self, conversation_id: UUID) -> tuple[GenerationTurn, ...]:
        statement = (
            select(MessageModel)
            .where(
                MessageModel.conversation_id == conversation_id,
                MessageModel.status == MessageStatus.COMPLETED.value,
            )
            .order_by(MessageModel.ordinal.desc())
            .limit(MAX_GENERATION_TURNS)
        )
        messages = (await self._session.scalars(statement)).all()
        turns_newest_first: list[GenerationTurn] = []
        input_bytes = 0
        for message in messages:
            if not message.content.strip():
                continue
            message_bytes = len(message.content.encode("utf-8"))
            if input_bytes + message_bytes > MAX_GENERATION_INPUT_BYTES:
                if not turns_newest_first:
                    raise ValueError("latest generation turn exceeds the inference payload limit")
                break
            turns_newest_first.append(
                GenerationTurn(
                    InferenceSpeaker.PARTNER
                    if message.speaker == Speaker.PARTNER.value
                    else InferenceSpeaker.SELF,
                    message.content,
                )
            )
            input_bytes += message_bytes
        return tuple(reversed(turns_newest_first))

    async def reserve_inference_capacity(
        self,
        principal: ConversationPrincipal,
        model: ModelId,
        *,
        global_limit: int,
        guest_limit: int,
    ) -> bool:
        await self._session.execute(
            select(func.pg_advisory_xact_lock(INFERENCE_ADMISSION_LOCK_KEY))
        )
        active_statuses = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)
        global_count = await self._session.scalar(
            select(func.count())
            .select_from(InferenceRunModel)
            .where(
                InferenceRunModel.requested_model == model.value,
                InferenceRunModel.status.in_(active_statuses),
            )
        )
        if (global_count or 0) >= global_limit:
            return False
        if principal.kind is PrincipalKind.USER:
            return True
        guest_count = await self._session.scalar(
            select(func.count())
            .select_from(InferenceRunModel)
            .join(ConversationModel, ConversationModel.id == InferenceRunModel.conversation_id)
            .where(
                ConversationModel.guest_session_id == principal.id,
                InferenceRunModel.requested_model == model.value,
                InferenceRunModel.status.in_(active_statuses),
            )
        )
        return (guest_count or 0) < guest_limit

    async def add_inference_outbox(self, run_id: UUID, payload: str) -> None:
        self._session.add(InferenceOutboxModel(run_id=run_id, payload=payload))
        await self._session.flush()

    async def pending_inference_outbox(self, *, limit: int = 32) -> list[PendingInferenceOutbox]:
        statement = (
            select(InferenceOutboxModel)
            .join(InferenceRunModel, InferenceRunModel.id == InferenceOutboxModel.run_id)
            .where(
                InferenceOutboxModel.published_at.is_(None),
                InferenceRunModel.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
            )
            .order_by(InferenceOutboxModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return [PendingInferenceOutbox(id=row.id, payload=row.payload) for row in rows]

    async def mark_outbox_published(self, outbox_id: UUID) -> None:
        row = await self._session.get(InferenceOutboxModel, outbox_id)
        if row is None:
            return
        row.publish_attempts += 1
        row.published_at = datetime.now(timezone.utc)
        row.payload = ""
        row.last_error = None
        await self._session.flush()

    async def mark_outbox_failed(self, outbox_id: UUID, error: str) -> None:
        row = await self._session.get(InferenceOutboxModel, outbox_id)
        if row is None:
            return
        row.publish_attempts += 1
        row.last_error = error[:500]
        await self._session.flush()

    async def project_inference_event(self, event: GenerationEvent) -> InferenceProjectionResult:
        statement = (
            select(InferenceRunModel, ConversationModel)
            .join(ConversationModel, ConversationModel.id == InferenceRunModel.conversation_id)
            .where(InferenceRunModel.id == event.run_id)
            .with_for_update()
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return InferenceProjectionResult(InferenceEventDisposition.IGNORE)
        run, conversation = row

        disposition = classify_inference_event(
            attempt_id=run.attempt_id,
            last_sequence=run.last_event_sequence,
            last_event_id=run.last_event_id,
            last_event_type=run.last_event_type,
            run_status=run.status,
            event=event,
        )
        if disposition in {InferenceEventDisposition.IGNORE, InferenceEventDisposition.DEFER}:
            return InferenceProjectionResult(disposition)

        output = await self._session.get(MessageModel, run.output_message_id)
        if output is None:
            return InferenceProjectionResult(InferenceEventDisposition.IGNORE)
        if disposition is InferenceEventDisposition.APPLY:
            self._apply_event(run, output, conversation, event)
            run.last_event_sequence = event.sequence
            run.last_event_id = event.id
            run.last_event_type = event.type.value
            await self._session.flush()

        principal = ConversationPrincipal(
            PrincipalKind.USER if conversation.owner_user_id else PrincipalKind.GUEST,
            conversation.owner_user_id or conversation.guest_session_id,
        )
        return InferenceProjectionResult(
            disposition,
            InferenceProjection(
                principal=principal,
                conversation_id=conversation.id,
                run_id=run.id,
                output_message_id=output.id,
                content=output.content,
            ),
        )

    async def expire_inference_runs(
        self, now: datetime, *, limit: int = 32
    ) -> list[InferenceProjection]:
        statement = (
            select(InferenceRunModel, ConversationModel)
            .join(ConversationModel, ConversationModel.id == InferenceRunModel.conversation_id)
            .where(
                InferenceRunModel.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
                InferenceRunModel.lease_expires_at.is_not(None),
                InferenceRunModel.lease_expires_at <= now,
            )
            .order_by(InferenceRunModel.lease_expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(statement)).all()
        projections: list[InferenceProjection] = []
        for run, conversation in rows:
            output = await self._session.get(MessageModel, run.output_message_id)
            if output is None:
                continue
            run.status = RunStatus.FAILED.value
            run.error_code = "inference_timeout"
            run.finish_reason = "error"
            run.finished_at = now
            run.lease_expires_at = None
            output.status = MessageStatus.FAILED.value
            conversation.last_activity_at = now
            projections.append(
                InferenceProjection(
                    principal=ConversationPrincipal(
                        PrincipalKind.USER if conversation.owner_user_id else PrincipalKind.GUEST,
                        conversation.owner_user_id or conversation.guest_session_id,
                    ),
                    conversation_id=conversation.id,
                    run_id=run.id,
                    output_message_id=output.id,
                    content=output.content,
                )
            )
        await self._session.flush()
        return projections

    @staticmethod
    def _apply_event(
        run: InferenceRunModel,
        output: MessageModel,
        conversation: ConversationModel,
        event: GenerationEvent,
    ) -> None:
        now = datetime.now(timezone.utc)
        if event.type is GenerationEventType.STARTED:
            run.status = RunStatus.RUNNING.value
            run.started_at = run.started_at or now
            run.resolved_model = event.resolved_model or run.resolved_model
            run.input_tokens = event.input_tokens
            run.lease_expires_at = now + timedelta(minutes=3)
            return
        if event.type is GenerationEventType.HEARTBEAT:
            run.lease_expires_at = now + timedelta(minutes=3)
            return
        if event.type is GenerationEventType.DELTA:
            run.status = RunStatus.RUNNING.value
            run.partial_output += event.delta or ""
            run.output_tokens = event.output_tokens
            run.lease_expires_at = now + timedelta(minutes=3)
            output.content = run.partial_output
            return
        if event.type is GenerationEventType.COMPLETED:
            content = event.content if event.content is not None else run.partial_output
            run.partial_output = content
            run.status = RunStatus.COMPLETED.value
            run.output_tokens = event.output_tokens
            run.finish_reason = event.finish_reason.value if event.finish_reason else None
            run.finished_at = now
            run.lease_expires_at = None
            output.content = content
            output.status = MessageStatus.COMPLETED.value
            conversation.last_activity_at = now
            return
        if event.type is GenerationEventType.FAILED:
            run.status = RunStatus.FAILED.value
            run.error_code = event.error_code
            run.finish_reason = event.finish_reason.value if event.finish_reason else "error"
            run.finished_at = now
            run.lease_expires_at = None
            output.status = MessageStatus.FAILED.value

    async def claim_queued_run(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        run_id: UUID,
    ) -> tuple[InferenceRun, str | None]:
        statement = (
            select(InferenceRunModel)
            .join(
                ConversationModel,
                ConversationModel.id == InferenceRunModel.conversation_id,
            )
            .where(
                InferenceRunModel.id == run_id,
                InferenceRunModel.conversation_id == conversation_id,
                ConversationModel.status == "active",
                self._owned_by(principal),
            )
            .with_for_update()
        )
        run = await self._session.scalar(statement)
        if run is None:
            raise ConversationNotFoundError
        if run.status != RunStatus.QUEUED.value:
            return self._to_run(run), None

        input_message = await self._session.get(MessageModel, run.input_message_id)
        output = await self._session.get(MessageModel, run.output_message_id)
        if input_message is None or output is None:
            raise ConversationNotFoundError
        run.status = RunStatus.RUNNING.value
        run.started_at = datetime.now(timezone.utc)
        await self._session.flush()
        return self._to_run(run), input_message.content

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
        run.lease_expires_at = None
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
        run.lease_expires_at = None
        if output is not None:
            output.status = MessageStatus.FAILED.value
        await self._session.flush()

    async def _locked_conversation(
        self, principal: ConversationPrincipal, conversation_id: UUID
    ) -> ConversationModel:
        statement = (
            select(ConversationModel)
            .where(
                ConversationModel.id == conversation_id,
                self._owned_by(principal),
                ConversationModel.status == "active",
            )
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
            attempt_id=model.attempt_id,
            requested_model=ModelId(model.requested_model),
            resolved_model=model.resolved_model,
            status=RunStatus(model.status),
            created_at=model.created_at,
        )


def _title_from(content: str) -> str:
    compact = " ".join(content.split())
    return compact if len(compact) <= 36 else f"{compact[:35]}…"
