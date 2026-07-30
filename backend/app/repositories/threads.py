from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sodai_contracts.inference import (
    MAX_GENERATION_INPUT_BYTES,
    MAX_GENERATION_TURNS,
    GenerationEvent,
    GenerationEventType,
    GenerationTurn,
    InferenceSpeaker,
)
from sqlalchemy import and_, case, func, or_, select, true
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.answerers import (
    AnswererDefinition,
    AnswererId,
    RuntimeKind,
    get_answerer,
)
from app.domain.execution_events import (
    EventDisposition,
    ExecutionProjection,
    PendingOutboxEvent,
    ProjectionResult,
    classify_generation_event,
)
from app.domain.inference_jobs import (
    GENERATION_CANCELLATION_OUTBOX_TOPIC,
    GENERATION_OUTBOX_TOPIC,
)
from app.domain.principals import Principal, PrincipalKind
from app.domain.reasoning import ReasoningEffort
from app.domain.responses import (
    Execution,
    ExecutionRetry,
    ResponseCreation,
    ResponseRequest,
    ResponseStatus,
)
from app.domain.threads import (
    Actor,
    ActorKind,
    Entry,
    EntryKind,
    SpaceSummary,
    Thread,
    ThreadSearchHit,
    ThreadSearchPage,
    ThreadSearchSource,
    ThreadSummary,
)
from app.models.humans import HumanTaskModel
from app.models.platform import (
    ActorModel,
    EntryTextContentModel,
    ExecutionModel,
    ModelExecutionModel,
    OutboxEventModel,
    ResponseContextItemModel,
    ResponseRequestModel,
    SpaceMembershipModel,
    SpaceModel,
    ThreadEntryModel,
    ThreadModel,
    ThreadParticipantModel,
)
from app.repositories.humans import CancelledHumanClaim, SqlAlchemyHumanRepository
from app.repositories.response_completion import complete_response, persist_response_entry

EXECUTION_ADMISSION_LOCK_KEY = 0x534F44414902


class ThreadNotFoundError(Exception):
    pass


class ThreadBusyError(Exception):
    pass


class ResponseRequestNotFoundError(Exception):
    pass


class ResponseNotRetryableError(Exception):
    pass


class GenerationCapacityExceededError(Exception):
    pass


class ExecutionNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PersonalContext:
    actor: ActorModel
    space: SpaceModel


@dataclass(frozen=True, slots=True)
class ExecutionCancellation:
    thread: Thread
    is_model: bool
    projection: ExecutionProjection | None
    human_claim: CancelledHumanClaim | None = None


class SqlAlchemyThreadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_personal_context(self, principal: Principal) -> PersonalContext:
        actor_id = uuid4()
        actor_values = {
            "id": actor_id,
            "kind": ActorKind.HUMAN.value,
            "key": f"human:{actor_id}",
            "name": "対話相手",
            "owner_user_id": principal.id if principal.kind is PrincipalKind.USER else None,
            "guest_session_id": principal.id if principal.kind is PrincipalKind.GUEST else None,
        }
        await self._session.execute(
            pg_insert(ActorModel).values(**actor_values).on_conflict_do_nothing()
        )
        actor = await self._session.scalar(
            select(ActorModel).where(self._actor_owned_by(principal))
        )
        if actor is None:
            raise RuntimeError("principal actor could not be resolved")

        space_values = {
            "id": uuid4(),
            "kind": "personal",
            "name": None,
            "owner_user_id": principal.id if principal.kind is PrincipalKind.USER else None,
            "guest_session_id": principal.id if principal.kind is PrincipalKind.GUEST else None,
            "status": "active",
        }
        await self._session.execute(
            pg_insert(SpaceModel).values(**space_values).on_conflict_do_nothing()
        )
        space = await self._session.scalar(
            select(SpaceModel).where(self._space_owned_by(principal))
        )
        if space is None:
            raise RuntimeError("personal space could not be resolved")
        await self._session.execute(
            pg_insert(SpaceMembershipModel)
            .values(space_id=space.id, actor_id=actor.id, role="owner", status="active")
            .on_conflict_do_nothing()
        )
        await self._session.flush()
        return PersonalContext(actor=actor, space=space)

    async def list_spaces(self, principal: Principal) -> list[SpaceSummary]:
        rows = (
            await self._session.scalars(
                select(SpaceModel)
                .where(self._space_accessible_by(principal), SpaceModel.status == "active")
                .order_by(SpaceModel.created_at)
            )
        ).all()
        return [self._to_space(row) for row in rows]

    async def create_thread_response(
        self,
        principal: Principal,
        context: PersonalContext,
        content: str,
        answerer: AnswererDefinition,
        *,
        execution_target: str,
        artifact_id: str | None,
        deadline_at: datetime | None,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> ResponseCreation:
        now = datetime.now(timezone.utc)
        thread = ThreadModel(
            id=uuid4(),
            space_id=context.space.id,
            created_by_actor_id=context.actor.id,
            title=_title_from(content),
            default_answerer=answerer.id.value,
            status="active",
            revision=1,
            last_activity_at=now,
            updated_at=now,
        )
        self._session.add(thread)
        self._session.add_all(
            [
                ThreadParticipantModel(
                    thread_id=thread.id, actor_id=context.actor.id, role="participant"
                ),
                ThreadParticipantModel(
                    thread_id=thread.id, actor_id=answerer.actor_id, role="answerer"
                ),
            ]
        )
        await self._session.flush()
        await self._create_response_models(
            thread,
            context.actor.id,
            content,
            answerer,
            execution_target=execution_target,
            artifact_id=artifact_id,
            deadline_at=deadline_at,
            reasoning_effort=reasoning_effort or answerer.default_reasoning_effort,
            ordinal=0,
        )
        await self._session.flush()
        return ResponseCreation(
            thread=await self.get(principal, thread.id),
            response=await self._latest_response(thread.id),
        )

    async def append_response(
        self,
        principal: Principal,
        thread_id: UUID,
        requester_actor_id: UUID,
        content: str,
        answerer: AnswererDefinition,
        *,
        execution_target: str,
        artifact_id: str | None,
        deadline_at: datetime | None,
        model_limit: int,
        guest_model_limit: int,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> ResponseCreation:
        thread = await self._locked_thread(principal, thread_id)
        active = await self._session.scalar(
            select(ResponseRequestModel.id).where(
                ResponseRequestModel.thread_id == thread_id,
                ResponseRequestModel.status.in_(["queued", "running"]),
            )
        )
        if active is not None:
            raise ThreadBusyError
        if answerer.runtime_kind is RuntimeKind.LOCAL_MODEL:
            admitted = await self.reserve_generation_capacity(
                principal,
                answerer.id,
                model_limit=model_limit,
                guest_model_limit=guest_model_limit,
            )
            if not admitted:
                raise GenerationCapacityExceededError
        await self._session.execute(
            pg_insert(ThreadParticipantModel)
            .values(thread_id=thread_id, actor_id=answerer.actor_id, role="answerer")
            .on_conflict_do_nothing()
        )
        last_ordinal = await self._session.scalar(
            select(func.max(ThreadEntryModel.ordinal)).where(
                ThreadEntryModel.thread_id == thread_id
            )
        )
        now = datetime.now(timezone.utc)
        thread.default_answerer = answerer.id.value
        thread.revision += 1
        thread.updated_at = now
        thread.last_activity_at = now
        await self._create_response_models(
            thread,
            requester_actor_id,
            content,
            answerer,
            execution_target=execution_target,
            artifact_id=artifact_id,
            deadline_at=deadline_at,
            reasoning_effort=reasoning_effort or answerer.default_reasoning_effort,
            ordinal=(last_ordinal if last_ordinal is not None else -1) + 1,
        )
        await self._session.flush()
        return ResponseCreation(
            thread=await self.get(principal, thread_id),
            response=await self._latest_response(thread_id),
        )

    async def retry_execution(
        self,
        principal: Principal,
        response_request_id: UUID,
        idempotency_key_hash: str,
        *,
        deadline_at: datetime,
        model_limit: int,
        guest_model_limit: int,
    ) -> ExecutionRetry:
        thread_id = await self._session.scalar(
            select(ResponseRequestModel.thread_id)
            .join(ThreadModel, ThreadModel.id == ResponseRequestModel.thread_id)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .where(
                ResponseRequestModel.id == response_request_id,
                self._space_accessible_by(principal),
                ThreadModel.status == "active",
            )
        )
        if thread_id is None:
            raise ResponseRequestNotFoundError
        try:
            thread = await self._locked_thread(principal, thread_id)
        except ThreadNotFoundError as error:
            raise ResponseRequestNotFoundError from error

        statement = (
            select(ResponseRequestModel)
            .where(
                ResponseRequestModel.id == response_request_id,
                ResponseRequestModel.thread_id == thread.id,
            )
            .options(
                selectinload(ResponseRequestModel.target_actor),
                selectinload(ResponseRequestModel.executions).selectinload(
                    ExecutionModel.model_execution
                ),
            )
            .with_for_update(of=ResponseRequestModel)
        )
        request = await self._session.scalar(statement)
        if request is None:
            raise ResponseRequestNotFoundError

        replayed = next(
            (
                execution
                for execution in request.executions
                if execution.idempotency_key_hash == idempotency_key_hash
            ),
            None,
        )
        if replayed is not None:
            return ExecutionRetry(
                thread=await self.get(principal, request.thread_id),
                response=self._to_response(request),
                execution=self._to_execution(replayed, AnswererId(request.requested_answerer)),
                replayed=True,
            )

        latest_request_id = await self._session.scalar(
            select(ResponseRequestModel.id)
            .where(ResponseRequestModel.thread_id == request.thread_id)
            .order_by(ResponseRequestModel.created_at.desc(), ResponseRequestModel.id.desc())
            .limit(1)
        )
        latest_execution = max(request.executions, key=lambda item: item.attempt_no)
        active_execution = next(
            (
                execution
                for execution in request.executions
                if execution.status
                in {
                    ResponseStatus.QUEUED.value,
                    ResponseStatus.RUNNING.value,
                }
            ),
            None,
        )
        if (
            latest_request_id != request.id
            or request.status != ResponseStatus.FAILED.value
            or latest_execution.status != ResponseStatus.FAILED.value
            or active_execution is not None
        ):
            raise ResponseNotRetryableError

        answerer = AnswererId(request.requested_answerer)
        answerer_definition = get_answerer(answerer)
        if answerer_definition is None or answerer_definition.runtime_kind is RuntimeKind.HUMAN:
            raise ResponseNotRetryableError
        if (
            answerer_definition is not None
            and answerer_definition.runtime_kind is RuntimeKind.LOCAL_MODEL
        ):
            admitted = await self.reserve_generation_capacity(
                principal,
                answerer,
                model_limit=model_limit,
                guest_model_limit=guest_model_limit,
            )
            if not admitted:
                raise GenerationCapacityExceededError

        execution = ExecutionModel(
            id=uuid4(),
            response_request_id=request.id,
            thread_id=request.thread_id,
            target_actor_id=request.target_actor_id,
            attempt_no=latest_execution.attempt_no + 1,
            attempt_id=uuid4(),
            idempotency_key_hash=idempotency_key_hash,
            execution_target=latest_execution.execution_target,
            status=ResponseStatus.QUEUED.value,
            partial_output="",
            deadline_at=deadline_at,
        )
        execution.model_execution = ModelExecutionModel(
            requested_model=latest_execution.model_execution.requested_model,
            resolved_model=None,
            artifact_id=latest_execution.model_execution.artifact_id,
        )
        request.executions.append(execution)
        request.status = ResponseStatus.QUEUED.value
        request.finished_at = None
        now = datetime.now(timezone.utc)
        thread.revision += 1
        thread.updated_at = now
        thread.last_activity_at = now
        await self._session.flush()
        refreshed_thread = await self.get(principal, request.thread_id)
        return ExecutionRetry(
            thread=refreshed_thread,
            response=self._to_response(request),
            execution=self._to_execution(execution, answerer),
            replayed=False,
        )

    async def cancel_execution(
        self,
        principal: Principal,
        execution_id: UUID,
    ) -> ExecutionCancellation:
        identity = (
            await self._session.execute(
                select(ExecutionModel.thread_id, HumanTaskModel.execution_id)
                .join(ThreadModel, ThreadModel.id == ExecutionModel.thread_id)
                .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .join(
                    ActorModel,
                    ActorModel.id == ResponseRequestModel.requester_actor_id,
                )
                .outerjoin(
                    HumanTaskModel,
                    HumanTaskModel.execution_id == ExecutionModel.id,
                )
                .where(
                    ExecutionModel.id == execution_id,
                    ThreadModel.status == "active",
                    self._space_accessible_by(principal),
                    self._actor_owned_by(principal),
                )
            )
        ).one_or_none()
        if identity is None:
            raise ExecutionNotFoundError
        thread_id, human_task_id = identity
        is_human = human_task_id is not None

        human_repository = SqlAlchemyHumanRepository(self._session)
        if is_human:
            # Human matching, answering, skipping, expiry, and requester
            # cancellation all serialize through the same lock before row locks.
            await human_repository.lock_matching()

        thread = await self._locked_thread(principal, thread_id)
        row = (
            await self._session.execute(
                select(
                    ExecutionModel,
                    ResponseRequestModel,
                    SpaceModel,
                )
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .join(SpaceModel, SpaceModel.id == thread.space_id)
                .where(
                    ExecutionModel.id == execution_id,
                    ExecutionModel.thread_id == thread.id,
                )
                .options(
                    selectinload(ResponseRequestModel.target_actor),
                )
                .with_for_update(of=(ExecutionModel, ResponseRequestModel))
            )
        ).one_or_none()
        if row is None:
            raise ExecutionNotFoundError
        execution, request, space = row
        if execution.status in {
            ResponseStatus.COMPLETED.value,
            ResponseStatus.FAILED.value,
            ResponseStatus.CANCELLED.value,
        }:
            return ExecutionCancellation(
                thread=await self.get(principal, thread.id),
                is_model=not is_human,
                projection=None,
            )

        now = datetime.now(timezone.utc)
        thread.revision += 1
        thread.updated_at = now
        thread.last_activity_at = now
        if execution.partial_output.strip():
            await persist_response_entry(
                self._session,
                execution,
                request,
                thread,
                execution.partial_output,
            )
        execution.status = ResponseStatus.CANCELLED.value
        execution.error_code = None
        execution.finish_reason = None
        execution.finished_at = now
        execution.lease_expires_at = None
        request.status = ResponseStatus.CANCELLED.value
        request.finished_at = now

        human_claim = None
        if is_human:
            human_claim = await human_repository.cancel_active_claim(execution.id, now)
        else:
            self._session.add(
                OutboxEventModel(
                    topic=GENERATION_CANCELLATION_OUTBOX_TOPIC,
                    aggregate_id=execution.id,
                    payload=str(execution.attempt_id),
                )
            )

        await self._session.flush()
        projection = await self._projection(execution, request, thread, space)
        return ExecutionCancellation(
            thread=await self.get(principal, thread.id),
            is_model=not is_human,
            projection=projection,
            human_claim=human_claim,
        )

    async def _create_response_models(
        self,
        thread: ThreadModel,
        requester_actor_id: UUID,
        content: str,
        answerer: AnswererDefinition,
        *,
        execution_target: str,
        artifact_id: str | None,
        deadline_at: datetime | None,
        reasoning_effort: ReasoningEffort,
        ordinal: int,
    ) -> None:
        input_entry = ThreadEntryModel(
            id=uuid4(),
            thread_id=thread.id,
            author_actor_id=requester_actor_id,
            kind=EntryKind.MESSAGE.value,
            ordinal=ordinal,
        )
        input_entry.text = EntryTextContentModel(content=content)
        self._session.add(input_entry)
        await self._session.flush()
        response_request = ResponseRequestModel(
            id=uuid4(),
            thread_id=thread.id,
            requester_actor_id=requester_actor_id,
            target_actor_id=answerer.actor_id,
            input_entry_id=input_entry.id,
            requested_answerer=answerer.id.value,
            reasoning_effort=reasoning_effort.value,
            status=ResponseStatus.QUEUED.value,
        )
        execution = ExecutionModel(
            id=uuid4(),
            response_request_id=response_request.id,
            thread_id=thread.id,
            target_actor_id=answerer.actor_id,
            attempt_no=1,
            attempt_id=uuid4(),
            execution_target=execution_target,
            status=ResponseStatus.QUEUED.value,
            partial_output="",
            deadline_at=deadline_at,
        )
        if answerer.runtime_kind is RuntimeKind.HUMAN:
            if answerer.required_human_rank is None:
                raise RuntimeError("Human answerer is missing its required rank")
            execution.human_task = HumanTaskModel(required_rank_level=answerer.required_human_rank)
        else:
            if artifact_id is None:
                raise RuntimeError("Model execution is missing its artifact")
            execution.model_execution = ModelExecutionModel(
                requested_model=answerer.id.value,
                resolved_model=None,
                artifact_id=artifact_id,
            )
        self._session.add_all([response_request, execution])
        await self._session.flush()
        await self._snapshot_context(
            response_request,
            full_thread=answerer.runtime_kind is RuntimeKind.HUMAN,
        )

    async def _snapshot_context(
        self, request: ResponseRequestModel, *, full_thread: bool = False
    ) -> None:
        statement = (
            select(ThreadEntryModel, EntryTextContentModel)
            .join(EntryTextContentModel, EntryTextContentModel.entry_id == ThreadEntryModel.id)
            .where(ThreadEntryModel.thread_id == request.thread_id)
            .order_by(ThreadEntryModel.ordinal.desc())
        )
        if not full_thread:
            statement = statement.limit(MAX_GENERATION_TURNS)
        rows = (await self._session.execute(statement)).all()
        selected: list[ThreadEntryModel] = []
        input_bytes = 0
        for entry, text_content in rows:
            size = len(text_content.content.encode("utf-8"))
            if not full_thread and input_bytes + size > MAX_GENERATION_INPUT_BYTES:
                if not selected:
                    raise ValueError("latest entry exceeds the generation context limit")
                break
            selected.append(entry)
            input_bytes += size
        for ordinal, entry in enumerate(reversed(selected)):
            self._session.add(
                ResponseContextItemModel(
                    response_request_id=request.id,
                    entry_id=entry.id,
                    thread_id=request.thread_id,
                    ordinal=ordinal,
                )
            )

    async def generation_turns(self, response_request_id: UUID) -> tuple[GenerationTurn, ...]:
        statement = (
            select(
                ThreadEntryModel.author_actor_id,
                EntryTextContentModel.content,
                ResponseRequestModel.target_actor_id,
            )
            .join(
                ResponseContextItemModel,
                and_(
                    ResponseContextItemModel.entry_id == ThreadEntryModel.id,
                    ResponseContextItemModel.thread_id == ThreadEntryModel.thread_id,
                ),
            )
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ResponseContextItemModel.response_request_id,
            )
            .join(EntryTextContentModel, EntryTextContentModel.entry_id == ThreadEntryModel.id)
            .where(ResponseContextItemModel.response_request_id == response_request_id)
            .order_by(ResponseContextItemModel.ordinal)
        )
        rows = (await self._session.execute(statement)).all()
        return tuple(
            GenerationTurn(
                InferenceSpeaker.SELF
                if author_actor_id == target_actor_id
                else InferenceSpeaker.PARTNER,
                content,
            )
            for author_actor_id, content, target_actor_id in rows
        )

    async def add_generation_outbox(self, execution_id: UUID, payload: str) -> None:
        self._session.add(
            OutboxEventModel(
                topic=GENERATION_OUTBOX_TOPIC,
                aggregate_id=execution_id,
                payload=payload,
            )
        )
        await self._session.flush()

    async def list(self, principal: Principal, *, limit: int = 50) -> list[ThreadSummary]:
        statement = (
            select(ThreadModel)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .where(self._space_accessible_by(principal), ThreadModel.status == "active")
            .order_by(ThreadModel.last_activity_at.desc())
            .limit(limit)
        )
        return [self._to_summary(row) for row in (await self._session.scalars(statement)).all()]

    async def search(
        self,
        principal: Principal,
        query: str,
        *,
        limit: int = 20,
    ) -> ThreadSearchPage:
        pattern = _literal_ilike_pattern(query)
        title_matches = ThreadModel.title.ilike(pattern, escape="\\")
        matching_entry = (
            select(
                ThreadEntryModel.id.label("entry_id"),
                EntryTextContentModel.content.label("content"),
            )
            .join(
                EntryTextContentModel,
                EntryTextContentModel.entry_id == ThreadEntryModel.id,
            )
            .where(
                ThreadEntryModel.thread_id == ThreadModel.id,
                EntryTextContentModel.content.ilike(pattern, escape="\\"),
            )
            .order_by(ThreadEntryModel.ordinal.desc())
            .limit(1)
            .lateral("matching_entry")
        )
        statement = (
            select(
                ThreadModel,
                matching_entry.c.entry_id,
                matching_entry.c.content,
            )
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .outerjoin(matching_entry, true())
            .where(
                self._space_accessible_by(principal),
                ThreadModel.status == "active",
                or_(title_matches, matching_entry.c.entry_id.is_not(None)),
            )
            .order_by(
                case((title_matches, 0), else_=1),
                ThreadModel.last_activity_at.desc(),
                ThreadModel.id,
            )
            .limit(limit + 1)
        )
        rows = (await self._session.execute(statement)).all()
        has_more = len(rows) > limit
        hits = []
        for thread, entry_id, content in rows[:limit]:
            source = ThreadSearchSource.ENTRY if entry_id is not None else ThreadSearchSource.TITLE
            hits.append(
                ThreadSearchHit(
                    thread=self._to_summary(thread),
                    source=source,
                    entry_id=entry_id,
                    snippet=_search_excerpt(content or thread.title, query),
                )
            )
        return ThreadSearchPage(items=tuple(hits), has_more=has_more)

    async def get(self, principal: Principal, thread_id: UUID) -> Thread:
        statement = (
            select(ThreadModel)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .where(
                ThreadModel.id == thread_id,
                self._space_accessible_by(principal),
                ThreadModel.status == "active",
            )
            .options(
                selectinload(ThreadModel.entries).selectinload(ThreadEntryModel.author),
                selectinload(ThreadModel.entries).selectinload(ThreadEntryModel.text),
                selectinload(ThreadModel.response_requests).selectinload(
                    ResponseRequestModel.target_actor
                ),
                selectinload(ThreadModel.response_requests)
                .selectinload(ResponseRequestModel.executions)
                .selectinload(ExecutionModel.model_execution),
            )
        )
        thread = await self._session.scalar(statement)
        if thread is None:
            raise ThreadNotFoundError
        return self._to_thread(thread)

    async def update_title(
        self, principal: Principal, thread_id: UUID, title: str
    ) -> ThreadSummary:
        thread = await self._locked_thread(principal, thread_id)
        now = datetime.now(timezone.utc)
        thread.title = title
        thread.revision += 1
        thread.updated_at = now
        await self._session.flush()
        return self._to_summary(thread)

    async def archive(self, principal: Principal, thread_id: UUID) -> ThreadSummary:
        thread = await self._locked_thread(principal, thread_id)
        thread.status = "archived"
        thread.revision += 1
        thread.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return self._to_summary(thread)

    async def reserve_generation_capacity(
        self,
        principal: Principal,
        answerer: AnswererId,
        *,
        model_limit: int,
        guest_model_limit: int,
    ) -> bool:
        await self._session.execute(
            select(func.pg_advisory_xact_lock(EXECUTION_ADMISSION_LOCK_KEY))
        )
        active = (ResponseStatus.QUEUED.value, ResponseStatus.RUNNING.value)
        model_count = await self._session.scalar(
            select(func.count())
            .select_from(ExecutionModel)
            .join(ModelExecutionModel)
            .where(
                ModelExecutionModel.requested_model == answerer.value,
                ExecutionModel.status.in_(active),
            )
        )
        if (model_count or 0) >= model_limit:
            return False
        if principal.kind is PrincipalKind.USER:
            return True
        guest_count = await self._session.scalar(
            select(func.count())
            .select_from(ExecutionModel)
            .join(ModelExecutionModel)
            .join(ThreadModel, ThreadModel.id == ExecutionModel.thread_id)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .where(
                SpaceModel.guest_session_id == principal.id,
                ModelExecutionModel.requested_model == answerer.value,
                ExecutionModel.status.in_(active),
            )
        )
        return (guest_count or 0) < guest_model_limit

    async def pending_outbox(self, *, limit: int = 32) -> list[PendingOutboxEvent]:
        statement = (
            select(OutboxEventModel)
            .join(ExecutionModel, ExecutionModel.id == OutboxEventModel.aggregate_id)
            .where(
                OutboxEventModel.topic == GENERATION_OUTBOX_TOPIC,
                OutboxEventModel.published_at.is_(None),
                OutboxEventModel.discarded_at.is_(None),
                ExecutionModel.status.in_(["queued", "running"]),
            )
            .order_by(OutboxEventModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return [
            PendingOutboxEvent(id=row.id, execution_id=row.aggregate_id, payload=row.payload)
            for row in rows
        ]

    async def pending_cancellation_outbox(
        self, *, limit: int = 32
    ) -> list[PendingOutboxEvent]:
        statement = (
            select(OutboxEventModel)
            .join(ExecutionModel, ExecutionModel.id == OutboxEventModel.aggregate_id)
            .where(
                OutboxEventModel.topic == GENERATION_CANCELLATION_OUTBOX_TOPIC,
                OutboxEventModel.published_at.is_(None),
                OutboxEventModel.discarded_at.is_(None),
                ExecutionModel.status == ResponseStatus.CANCELLED.value,
            )
            .order_by(OutboxEventModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.scalars(statement)).all()
        return [
            PendingOutboxEvent(id=row.id, execution_id=row.aggregate_id, payload=row.payload)
            for row in rows
        ]

    async def discard_terminal_outbox(self, *, limit: int = 32) -> int:
        statement = (
            select(OutboxEventModel)
            .join(ExecutionModel, ExecutionModel.id == OutboxEventModel.aggregate_id)
            .where(
                OutboxEventModel.topic == GENERATION_OUTBOX_TOPIC,
                OutboxEventModel.published_at.is_(None),
                OutboxEventModel.discarded_at.is_(None),
                ExecutionModel.status.in_(["completed", "failed", "cancelled"]),
            )
            .order_by(OutboxEventModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.scalars(statement)).all()
        discarded_at = datetime.now(timezone.utc)
        for row in rows:
            row.discarded_at = discarded_at
            row.payload = ""
            row.last_error = "execution_terminated_before_dispatch"
        await self._session.flush()
        return len(rows)

    async def mark_outbox_published(self, outbox_id: UUID) -> None:
        row = await self._session.get(OutboxEventModel, outbox_id)
        if row is None:
            return
        row.publish_attempts += 1
        row.published_at = datetime.now(timezone.utc)
        row.payload = ""
        row.last_error = None
        await self._session.flush()

    async def mark_outbox_failed(self, outbox_id: UUID, error: str) -> None:
        row = await self._session.get(OutboxEventModel, outbox_id)
        if row is None:
            return
        row.publish_attempts += 1
        row.last_error = error[:500]
        await self._session.flush()

    async def project_generation_event(self, event: GenerationEvent) -> ProjectionResult:
        thread_id = await self._session.scalar(
            select(ExecutionModel.thread_id)
            .join(
                ModelExecutionModel,
                ModelExecutionModel.execution_id == ExecutionModel.id,
            )
            .where(ExecutionModel.id == event.execution_id)
        )
        if thread_id is None:
            return ProjectionResult(EventDisposition.IGNORE)
        thread = await self._session.scalar(
            select(ThreadModel).where(ThreadModel.id == thread_id).with_for_update()
        )
        if thread is None:
            return ProjectionResult(EventDisposition.IGNORE)
        statement = (
            select(
                ExecutionModel,
                ModelExecutionModel,
                ResponseRequestModel,
                SpaceModel,
            )
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .join(
                ModelExecutionModel,
                ModelExecutionModel.execution_id == ExecutionModel.id,
            )
            .join(SpaceModel, SpaceModel.id == thread.space_id)
            .where(
                ExecutionModel.id == event.execution_id,
                ExecutionModel.thread_id == thread.id,
            )
            .with_for_update(of=(ExecutionModel, ModelExecutionModel, ResponseRequestModel))
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return ProjectionResult(EventDisposition.IGNORE)
        execution, model_execution, request, space = row
        if event.thread_id != execution.thread_id:
            return ProjectionResult(EventDisposition.IGNORE)
        disposition = classify_generation_event(
            attempt_id=execution.attempt_id,
            last_sequence=execution.last_event_sequence,
            last_event_id=execution.last_event_id,
            last_event_type=execution.last_event_type,
            execution_status=execution.status,
            event=event,
        )
        if disposition in {EventDisposition.IGNORE, EventDisposition.DEFER}:
            return ProjectionResult(disposition)
        if disposition is EventDisposition.APPLY:
            await self._apply_event(
                execution,
                model_execution,
                request,
                thread,
                event,
            )
            execution.last_event_sequence = event.sequence
            execution.last_event_id = event.id
            execution.last_event_type = event.type.value
            await self._session.flush()
        return ProjectionResult(
            disposition,
            await self._projection(execution, request, thread, space),
        )

    async def _apply_event(
        self,
        execution: ExecutionModel,
        model_execution: ModelExecutionModel,
        request: ResponseRequestModel,
        thread: ThreadModel,
        event: GenerationEvent,
    ) -> None:
        now = datetime.now(timezone.utc)
        thread.revision += 1
        thread.updated_at = now
        if event.type is GenerationEventType.STARTED:
            execution.status = ResponseStatus.RUNNING.value
            execution.started_at = execution.started_at or now
            execution.lease_expires_at = now + timedelta(minutes=3)
            execution.input_tokens = event.input_tokens
            model_execution.resolved_model = event.resolved_model
            request.status = ResponseStatus.RUNNING.value
            request.started_at = request.started_at or now
            return
        if event.type is GenerationEventType.HEARTBEAT:
            execution.lease_expires_at = now + timedelta(minutes=3)
            return
        if event.type is GenerationEventType.DELTA:
            execution.partial_output += event.delta or ""
            execution.output_tokens = event.output_tokens
            execution.lease_expires_at = now + timedelta(minutes=3)
            return
        if event.type is GenerationEventType.COMPLETED:
            content = event.content if event.content is not None else execution.partial_output
            if not content.strip():
                self._fail_execution(execution, request, thread, now, "empty_generation")
                return
            await complete_response(self._session, execution, request, thread, content, now)
            execution.output_tokens = event.output_tokens
            execution.finish_reason = event.finish_reason.value if event.finish_reason else None
            return
        self._fail_execution(
            execution,
            request,
            thread,
            now,
            event.error_code or "generation_failed",
        )

    @staticmethod
    def _fail_execution(
        execution: ExecutionModel,
        request: ResponseRequestModel,
        thread: ThreadModel,
        now: datetime,
        error_code: str,
    ) -> None:
        execution.status = ResponseStatus.FAILED.value
        execution.error_code = error_code
        execution.finish_reason = "error"
        execution.finished_at = now
        execution.lease_expires_at = None
        request.status = ResponseStatus.FAILED.value
        request.finished_at = now
        thread.last_activity_at = now

    async def expire_executions(
        self, now: datetime, *, limit: int = 32
    ) -> list[ExecutionProjection]:
        expiration_filter = or_(
            and_(
                ExecutionModel.status == ResponseStatus.QUEUED.value,
                ExecutionModel.deadline_at <= now,
            ),
            and_(
                ExecutionModel.status == ResponseStatus.RUNNING.value,
                ExecutionModel.lease_expires_at <= now,
            ),
        )
        candidates = (
            await self._session.execute(
                select(ExecutionModel.id, ExecutionModel.thread_id)
                .join(
                    ModelExecutionModel,
                    ModelExecutionModel.execution_id == ExecutionModel.id,
                )
                .where(expiration_filter)
                .order_by(ExecutionModel.deadline_at)
                .limit(limit)
            )
        ).all()
        projections: list[ExecutionProjection] = []
        for execution_id, thread_id in candidates:
            thread = await self._session.scalar(
                select(ThreadModel)
                .where(ThreadModel.id == thread_id)
                .with_for_update(skip_locked=True)
            )
            if thread is None:
                continue
            statement = (
                select(ExecutionModel, ResponseRequestModel, SpaceModel)
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .join(
                    ModelExecutionModel,
                    ModelExecutionModel.execution_id == ExecutionModel.id,
                )
                .join(SpaceModel, SpaceModel.id == thread.space_id)
                .where(
                    ExecutionModel.id == execution_id,
                    ExecutionModel.thread_id == thread.id,
                    expiration_filter,
                )
                .options(selectinload(ExecutionModel.model_execution))
                .with_for_update(
                    of=(ExecutionModel, ResponseRequestModel),
                    skip_locked=True,
                )
            )
            row = (await self._session.execute(statement)).one_or_none()
            if row is None:
                continue
            execution, request, space = row
            thread.revision += 1
            thread.updated_at = now
            self._fail_execution(execution, request, thread, now, "generation_timeout")
            projections.append(await self._projection(execution, request, thread, space))
        await self._session.flush()
        return projections

    async def _projection(
        self,
        execution: ExecutionModel,
        request: ResponseRequestModel,
        thread: ThreadModel,
        space: SpaceModel,
    ) -> ExecutionProjection:
        return ExecutionProjection(
            principals=await self._space_principals(space.id),
            space_id=space.id,
            thread_id=thread.id,
            thread_revision=thread.revision,
            response_request_id=request.id,
            execution_id=execution.id,
            attempt_id=execution.attempt_id,
            attempt_no=execution.attempt_no,
            target_actor_id=request.target_actor_id,
            result_entry_id=execution.result_entry_id,
            content=execution.partial_output,
            status=execution.status,
            error_code=execution.error_code,
        )

    async def _space_principals(self, space_id: UUID) -> tuple[Principal, ...]:
        statement = (
            select(ActorModel.owner_user_id, ActorModel.guest_session_id)
            .join(SpaceMembershipModel, SpaceMembershipModel.actor_id == ActorModel.id)
            .where(
                SpaceMembershipModel.space_id == space_id,
                SpaceMembershipModel.status == "active",
                ActorModel.kind == ActorKind.HUMAN.value,
            )
        )
        principals = {
            Principal(
                PrincipalKind.USER if user_id is not None else PrincipalKind.GUEST,
                user_id or guest_id,
            )
            for user_id, guest_id in (await self._session.execute(statement)).all()
            if user_id is not None or guest_id is not None
        }
        return tuple(principals)

    async def _latest_response(self, thread_id: UUID) -> ResponseRequest:
        statement = (
            select(ResponseRequestModel)
            .join(
                ThreadEntryModel,
                and_(
                    ThreadEntryModel.id == ResponseRequestModel.input_entry_id,
                    ThreadEntryModel.thread_id == ResponseRequestModel.thread_id,
                ),
            )
            .where(ResponseRequestModel.thread_id == thread_id)
            .order_by(ThreadEntryModel.ordinal.desc())
            .limit(1)
            .options(
                selectinload(ResponseRequestModel.target_actor),
                selectinload(ResponseRequestModel.executions).selectinload(
                    ExecutionModel.model_execution
                ),
            )
        )
        model = await self._session.scalar(statement)
        if model is None:
            raise RuntimeError("response request was not persisted")
        return self._to_response(model)

    async def _locked_thread(self, principal: Principal, thread_id: UUID) -> ThreadModel:
        conditions = [ThreadModel.id == thread_id, self._space_accessible_by(principal)]
        conditions.append(ThreadModel.status == "active")
        statement = (
            select(ThreadModel)
            .join(SpaceModel, SpaceModel.id == ThreadModel.space_id)
            .where(*conditions)
            .with_for_update()
        )
        thread = await self._session.scalar(statement)
        if thread is None:
            raise ThreadNotFoundError
        return thread

    @staticmethod
    def _actor_owned_by(principal: Principal):
        if principal.kind is PrincipalKind.USER:
            return ActorModel.owner_user_id == principal.id
        return ActorModel.guest_session_id == principal.id

    @staticmethod
    def _space_owned_by(principal: Principal):
        if principal.kind is PrincipalKind.USER:
            return SpaceModel.owner_user_id == principal.id
        return SpaceModel.guest_session_id == principal.id

    @classmethod
    def _space_accessible_by(cls, principal: Principal):
        return (
            select(SpaceMembershipModel.space_id)
            .join(ActorModel, ActorModel.id == SpaceMembershipModel.actor_id)
            .where(
                SpaceMembershipModel.space_id == SpaceModel.id,
                SpaceMembershipModel.status == "active",
                cls._actor_owned_by(principal),
            )
            .exists()
        )

    @staticmethod
    def _to_space(model: SpaceModel) -> SpaceSummary:
        return SpaceSummary(
            id=model.id, kind=model.kind, name=model.name, created_at=model.created_at
        )

    @staticmethod
    def _to_summary(model: ThreadModel) -> ThreadSummary:
        return ThreadSummary(
            id=model.id,
            space_id=model.space_id,
            title=model.title,
            answerer=AnswererId(model.default_answerer),
            revision=model.revision,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_activity_at=model.last_activity_at,
        )

    @classmethod
    def _to_thread(cls, model: ThreadModel) -> Thread:
        ordered_entries = sorted(model.entries, key=lambda entry: entry.ordinal)
        entry_ordinals = {entry.id: entry.ordinal for entry in ordered_entries}
        entry_responses: dict[UUID, tuple[AnswererId, ResponseStatus]] = {}
        for request in model.response_requests:
            for execution in request.executions:
                if execution.result_entry_id is None:
                    continue
                entry_responses[execution.result_entry_id] = (
                    AnswererId(request.requested_answerer),
                    ResponseStatus(execution.status),
                )
        latest = max(
            model.response_requests,
            key=lambda item: entry_ordinals.get(item.input_entry_id, -1),
            default=None,
        )
        return Thread(
            id=model.id,
            space_id=model.space_id,
            title=model.title,
            answerer=AnswererId(model.default_answerer),
            revision=model.revision,
            entries=tuple(
                cls._to_entry(entry, entry_responses.get(entry.id))
                for entry in ordered_entries
            ),
            latest_response=cls._to_response(latest) if latest is not None else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_activity_at=model.last_activity_at,
        )

    @staticmethod
    def _to_entry(
        model: ThreadEntryModel,
        response: tuple[AnswererId, ResponseStatus] | None = None,
    ) -> Entry:
        return Entry(
            id=model.id,
            thread_id=model.thread_id,
            author=Actor(
                id=model.author.id,
                kind=ActorKind(model.author.kind),
                key=model.author.key,
                name=model.author.name,
            ),
            kind=EntryKind(model.kind),
            content=model.text.content,
            ordinal=model.ordinal,
            created_at=model.created_at,
            answerer=response[0] if response else None,
            response_status=response[1] if response else None,
        )

    @classmethod
    def _to_response(cls, model: ResponseRequestModel) -> ResponseRequest:
        execution = max(model.executions, key=lambda item: item.attempt_no)
        return ResponseRequest(
            id=model.id,
            thread_id=model.thread_id,
            input_entry_id=model.input_entry_id,
            requested_answerer=AnswererId(model.requested_answerer),
            reasoning_effort=ReasoningEffort(model.reasoning_effort),
            target_actor=Actor(
                id=model.target_actor.id,
                kind=ActorKind(model.target_actor.kind),
                key=model.target_actor.key,
                name=model.target_actor.name,
            ),
            status=ResponseStatus(model.status),
            execution=cls._to_execution(execution, AnswererId(model.requested_answerer)),
            created_at=model.created_at,
        )

    @staticmethod
    def _to_execution(model: ExecutionModel, answerer: AnswererId) -> Execution:
        model_execution = model.model_execution
        return Execution(
            id=model.id,
            response_request_id=model.response_request_id,
            thread_id=model.thread_id,
            result_entry_id=model.result_entry_id,
            answerer=answerer,
            target=model.execution_target,
            status=ResponseStatus(model.status),
            attempt_no=model.attempt_no,
            attempt_id=model.attempt_id,
            partial_output=model.partial_output,
            resolved_model=(model_execution.resolved_model if model_execution else None),
            artifact_id=(model_execution.artifact_id if model_execution else None),
            error_code=model.error_code,
            created_at=model.created_at,
        )


def _title_from(content: str) -> str:
    compact = " ".join(content.split())
    return compact if len(compact) <= 36 else f"{compact[:35]}…"


def _literal_ilike_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_excerpt(content: str, query: str, *, max_length: int = 160) -> str:
    compact = " ".join(content.split())
    if len(compact) <= max_length:
        return compact

    compact_query = " ".join(query.split())
    match_index = compact.casefold().find(compact_query.casefold())
    if match_index < 0:
        match_index = 0
    start = max(0, min(match_index - max_length // 3, len(compact) - max_length))
    end = start + max_length
    return f"{'…' if start else ''}{compact[start:end]}{'…' if end < len(compact) else ''}"
