from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from hashlib import sha256
from uuid import UUID

from sodai_contracts.inference import GenerationJob
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.domain.answerers import (
    AnswererAudience,
    AnswererDefinition,
    AnswererId,
    AvailableAnswerer,
    RuntimeKind,
    get_answerer,
    get_default_answerer,
    list_available_answerers,
)
from app.domain.execution_events import ExecutionProjection
from app.domain.principals import Principal, PrincipalKind
from app.domain.reasoning import ReasoningEffort
from app.domain.responses import Execution, ResponseCreation, ResponseRequest
from app.domain.threads import SpaceSummary, Thread, ThreadSearchPage, ThreadSummary
from app.repositories.threads import GenerationCapacityExceededError, SqlAlchemyThreadRepository
from app.services.human import get_human_service
from app.services.inference.asuka import ASUKA_PSEUDO_ARTIFACT_ID
from app.services.inference.billing import InferenceBillingService
from app.services.inference.deployment import ModelDeploymentError, ModelDeploymentRegistry
from app.services.realtime import realtime_hub


class AnswererAccessError(Exception):
    pass


class AnswererUnavailableError(Exception):
    pass


class GenerationCapacityError(Exception):
    pass


class ReasoningEffortAccessError(Exception):
    pass


class ThreadService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        deployments: ModelDeploymentRegistry,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._deployments = deployments
        self._settings = settings

    async def create(
        self,
        principal: Principal,
        content: str,
        requested_answerer: AnswererId | None,
        requested_reasoning_effort: ReasoningEffort | None = None,
    ) -> ResponseCreation:
        answerer = self.select_answerer(principal, requested_answerer)
        reasoning_effort = self.select_reasoning_effort(
            answerer,
            requested_reasoning_effort,
        )
        execution_target, artifact_id = self._resolve_runtime(answerer)
        deadline = self._execution_deadline(answerer, reasoning_effort)
        async with self._session_factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            context = await repository.ensure_personal_context(principal)
            await self._reserve_capacity(repository, principal, answerer)
            creation = await repository.create_thread_response(
                principal,
                context,
                content.strip(),
                answerer,
                execution_target=execution_target,
                artifact_id=artifact_id,
                deadline_at=deadline,
                reasoning_effort=reasoning_effort,
            )
            if answerer.runtime_kind is not RuntimeKind.HUMAN:
                await InferenceBillingService(session).register(
                    principal,
                    creation.response.execution,
                    answerer.tariff,
                )
                await self._enqueue_generation(
                    repository,
                    creation.thread,
                    creation.response,
                    answerer,
                    self._required_artifact(artifact_id),
                    self._required_deadline(deadline),
                )
            await session.commit()
        await realtime_hub.publish(
            principal,
            event_type="thread.created",
            space_id=creation.thread.space_id,
            thread_id=creation.thread.id,
            thread_revision=creation.thread.revision,
            response_request_id=creation.response.id,
            execution_id=creation.response.execution.id,
            data={
                "title": creation.thread.title,
                "answerer": creation.thread.answerer.value,
                "created_at": creation.thread.created_at.isoformat(),
                "updated_at": creation.thread.updated_at.isoformat(),
                "last_activity_at": creation.thread.last_activity_at.isoformat(),
            },
        )
        if answerer.runtime_kind is RuntimeKind.HUMAN:
            await get_human_service().match_available_best_effort()
        return creation

    async def append(
        self,
        principal: Principal,
        thread_id: UUID,
        content: str,
        requested_answerer: AnswererId | None,
        requested_reasoning_effort: ReasoningEffort | None = None,
    ) -> ResponseCreation:
        answerer = self.select_answerer(principal, requested_answerer)
        reasoning_effort = self.select_reasoning_effort(
            answerer,
            requested_reasoning_effort,
        )
        execution_target, artifact_id = self._resolve_runtime(answerer)
        deadline = self._execution_deadline(answerer, reasoning_effort)
        async with self._session_factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            context = await repository.ensure_personal_context(principal)
            try:
                creation = await repository.append_response(
                    principal,
                    thread_id,
                    context.actor.id,
                    content.strip(),
                    answerer,
                    execution_target=execution_target,
                    artifact_id=artifact_id,
                    deadline_at=deadline,
                    reasoning_effort=reasoning_effort,
                    model_limit=self._settings.inference_model_active_limit,
                    guest_model_limit=self._settings.inference_guest_model_active_limit,
                )
            except GenerationCapacityExceededError as error:
                raise GenerationCapacityError from error
            if answerer.runtime_kind is not RuntimeKind.HUMAN:
                await InferenceBillingService(session).register(
                    principal,
                    creation.response.execution,
                    answerer.tariff,
                )
                await self._enqueue_generation(
                    repository,
                    creation.thread,
                    creation.response,
                    answerer,
                    self._required_artifact(artifact_id),
                    self._required_deadline(deadline),
                )
            await session.commit()
        await realtime_hub.publish(
            principal,
            event_type="entry.created",
            space_id=creation.thread.space_id,
            thread_id=thread_id,
            thread_revision=creation.thread.revision,
            response_request_id=creation.response.id,
            execution_id=creation.response.execution.id,
            data={
                "input_entry_id": str(creation.response.input_entry_id),
                "answerer": answerer.id.value,
                "last_activity_at": creation.thread.last_activity_at.isoformat(),
            },
        )
        if answerer.runtime_kind is RuntimeKind.HUMAN:
            await get_human_service().match_available_best_effort()
        return creation

    async def retry(
        self,
        principal: Principal,
        response_request_id: UUID,
        idempotency_key: str,
    ) -> Execution:
        deadline = self._generation_deadline()
        key_hash = sha256(idempotency_key.encode("utf-8")).hexdigest()
        async with self._session_factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            try:
                retry = await repository.retry_execution(
                    principal,
                    response_request_id,
                    key_hash,
                    deadline_at=deadline,
                    model_limit=self._settings.inference_model_active_limit,
                    guest_model_limit=self._settings.inference_guest_model_active_limit,
                )
            except GenerationCapacityExceededError as error:
                raise GenerationCapacityError from error
            if retry.replayed:
                await session.commit()
                return retry.execution

            answerer = get_answerer(retry.response.requested_answerer)
            if answerer is None:
                raise AnswererUnavailableError
            artifact_id = self._required_artifact(retry.execution.artifact_id)
            self._validate_retry_artifact(answerer, artifact_id)
            await InferenceBillingService(session).register(
                principal,
                retry.execution,
                answerer.tariff,
            )
            await self._enqueue_generation(
                repository,
                retry.thread,
                retry.response,
                answerer,
                artifact_id,
                deadline,
            )
            await session.commit()
        await realtime_hub.publish(
            principal,
            event_type="response.queued",
            space_id=retry.thread.space_id,
            thread_id=retry.thread.id,
            thread_revision=retry.thread.revision,
            response_request_id=retry.response.id,
            execution_id=retry.execution.id,
            data={
                "attempt_no": retry.execution.attempt_no,
                "target_actor_id": str(retry.response.target_actor.id),
                "last_activity_at": retry.thread.last_activity_at.isoformat(),
            },
        )
        return retry.execution

    async def cancel(
        self,
        principal: Principal,
        execution_id: UUID,
    ) -> Thread:
        async with self._session_factory() as session:
            cancellation = await SqlAlchemyThreadRepository(session).cancel_execution(
                principal,
                execution_id,
            )
            projection = cancellation.projection
            if projection is not None and cancellation.is_model:
                await InferenceBillingService(session).finalize(execution_id)
            await session.commit()

        if projection is None:
            return cancellation.thread
        await self._publish_cancellation(projection)
        if cancellation.human_claim is not None:
            human_claim = cancellation.human_claim
            await realtime_hub.publish(
                Principal(PrincipalKind.USER, human_claim.performer_user_id),
                event_type="human.assignment.cancelled",
                space_id=projection.space_id,
                thread_id=projection.thread_id,
                thread_revision=projection.thread_revision,
                response_request_id=projection.response_request_id,
                execution_id=projection.execution_id,
                data={
                    "claim_id": str(human_claim.claim_id),
                    "reason": "requester_cancelled",
                },
            )
            await get_human_service().match_available_best_effort()
        return cancellation.thread

    async def list_spaces(self, principal: Principal) -> list[SpaceSummary]:
        async with self._session_factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            await repository.ensure_personal_context(principal)
            spaces = await repository.list_spaces(principal)
            await session.commit()
            return spaces

    async def list(self, principal: Principal) -> list[ThreadSummary]:
        async with self._session_factory() as session:
            return await SqlAlchemyThreadRepository(session).list(principal)

    async def search(
        self,
        principal: Principal,
        query: str,
        *,
        limit: int,
    ) -> ThreadSearchPage:
        normalized = query.strip()
        if not normalized:
            raise ValueError("Search query cannot be blank")
        async with self._session_factory() as session:
            return await SqlAlchemyThreadRepository(session).search(
                principal,
                normalized,
                limit=limit,
            )

    async def get(self, principal: Principal, thread_id: UUID) -> Thread:
        async with self._session_factory() as session:
            return await SqlAlchemyThreadRepository(session).get(principal, thread_id)

    async def update_title(
        self, principal: Principal, thread_id: UUID, title: str
    ) -> ThreadSummary:
        normalized = title.strip()
        if not normalized:
            raise ValueError("Thread title cannot be blank")
        async with self._session_factory() as session:
            thread = await SqlAlchemyThreadRepository(session).update_title(
                principal, thread_id, normalized
            )
            await session.commit()
        await realtime_hub.publish(
            principal,
            event_type="thread.updated",
            space_id=thread.space_id,
            thread_id=thread.id,
            thread_revision=thread.revision,
            response_request_id=None,
            execution_id=None,
            data={"title": thread.title, "updated_at": thread.updated_at.isoformat()},
        )
        return thread

    async def archive(self, principal: Principal, thread_id: UUID) -> None:
        async with self._session_factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            thread = await repository.archive(principal, thread_id)
            await session.commit()
        await realtime_hub.publish(
            principal,
            event_type="thread.archived",
            space_id=thread.space_id,
            thread_id=thread.id,
            thread_revision=thread.revision,
            response_request_id=None,
            execution_id=None,
            data={},
        )

    async def _enqueue_generation(
        self,
        repository: SqlAlchemyThreadRepository,
        thread: Thread,
        response: ResponseRequest,
        answerer: AnswererDefinition,
        artifact_id: str,
        deadline: datetime,
    ) -> None:
        execution = response.execution
        job = GenerationJob.create(
            execution_id=execution.id,
            response_request_id=response.id,
            attempt_id=execution.attempt_id,
            thread_id=thread.id,
            answerer_actor_id=response.target_actor.id,
            model=answerer.runtime_name,
            artifact_id=artifact_id,
            turns=await repository.generation_turns(response.id),
            deadline=deadline,
        )
        await repository.add_generation_outbox(execution.id, job.to_json())

    @staticmethod
    async def _publish_cancellation(projection: ExecutionProjection) -> None:
        data = {
            "target_actor_id": str(projection.target_actor_id),
            "result_entry_id": (
                str(projection.result_entry_id) if projection.result_entry_id else None
            ),
            "content": projection.content,
        }
        for principal in projection.principals:
            await realtime_hub.publish(
                principal,
                event_type="response.cancelled",
                space_id=projection.space_id,
                thread_id=projection.thread_id,
                thread_revision=projection.thread_revision,
                response_request_id=projection.response_request_id,
                execution_id=projection.execution_id,
                data=data,
            )

    def _validate_retry_artifact(self, answerer: AnswererDefinition, artifact_id: str) -> None:
        if answerer.runtime_kind is RuntimeKind.PSEUDO_MODEL:
            if artifact_id != ASUKA_PSEUDO_ARTIFACT_ID:
                raise AnswererUnavailableError
            return
        try:
            self._deployments.resolve_artifact(answerer.runtime_name, artifact_id)
        except ModelDeploymentError as error:
            raise AnswererUnavailableError from error

    async def _reserve_capacity(
        self,
        repository: SqlAlchemyThreadRepository,
        principal: Principal,
        answerer: AnswererDefinition,
    ) -> None:
        if answerer.runtime_kind is not RuntimeKind.LOCAL_MODEL:
            return
        admitted = await repository.reserve_generation_capacity(
            principal,
            answerer.id,
            model_limit=self._settings.inference_model_active_limit,
            guest_model_limit=self._settings.inference_guest_model_active_limit,
        )
        if not admitted:
            raise GenerationCapacityError

    def _resolve_runtime(self, answerer: AnswererDefinition) -> tuple[str, str | None]:
        if answerer.runtime_kind is RuntimeKind.HUMAN:
            return f"human:{answerer.runtime_name}", None
        if answerer.runtime_kind is RuntimeKind.PSEUDO_MODEL:
            return f"pseudo:{answerer.runtime_name}", ASUKA_PSEUDO_ARTIFACT_ID
        try:
            deployment = self._deployments.resolve(answerer.runtime_name)
        except ModelDeploymentError as error:
            raise AnswererUnavailableError from error
        return f"local:{answerer.runtime_name}", deployment.artifact_id

    @staticmethod
    def available_answerers(principal: Principal) -> list[AvailableAnswerer]:
        return list_available_answerers(ThreadService._audience(principal))

    @staticmethod
    def select_answerer(principal: Principal, requested: AnswererId | None) -> AnswererDefinition:
        audience = ThreadService._audience(principal)
        answerer = (
            get_answerer(requested) if requested is not None else get_default_answerer(audience)
        )
        if answerer is None or audience not in answerer.audiences:
            raise AnswererAccessError
        return answerer

    @staticmethod
    def select_reasoning_effort(
        answerer: AnswererDefinition,
        requested: ReasoningEffort | None,
    ) -> ReasoningEffort:
        effort = requested or answerer.default_reasoning_effort
        if effort not in answerer.supported_reasoning_efforts:
            raise ReasoningEffortAccessError
        return effort

    @staticmethod
    def _audience(principal: Principal) -> AnswererAudience:
        return (
            AnswererAudience.AUTHENTICATED
            if principal.kind is PrincipalKind.USER
            else AnswererAudience.GUEST
        )

    def _generation_deadline(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            seconds=self._settings.inference_job_timeout_seconds
        )

    def _execution_deadline(
        self,
        answerer: AnswererDefinition,
        reasoning_effort: ReasoningEffort,
    ) -> datetime | None:
        if reasoning_effort not in answerer.supported_reasoning_efforts:
            raise ReasoningEffortAccessError
        if answerer.runtime_kind is RuntimeKind.HUMAN:
            return None
        return self._generation_deadline()

    @staticmethod
    def _required_artifact(artifact_id: str | None) -> str:
        if artifact_id is None:
            raise AnswererUnavailableError
        return artifact_id

    @staticmethod
    def _required_deadline(deadline: datetime | None) -> datetime:
        if deadline is None:
            raise AnswererUnavailableError
        return deadline


@lru_cache
def get_thread_service_singleton() -> ThreadService:
    settings = get_settings()
    return ThreadService(
        get_session_factory(),
        ModelDeploymentRegistry(settings.model_root),
        settings,
    )


def get_thread_service() -> ThreadService:
    return get_thread_service_singleton()
