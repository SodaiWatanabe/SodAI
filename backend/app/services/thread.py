from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
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
from app.domain.principals import Principal, PrincipalKind
from app.domain.responses import ResponseCreation
from app.domain.threads import SpaceSummary, Thread, ThreadSummary
from app.repositories.threads import SqlAlchemyThreadRepository
from app.services.inference.asuka import ASUKA_PSEUDO_ARTIFACT_ID
from app.services.inference.deployment import ModelDeploymentError, ModelDeploymentRegistry
from app.services.realtime import realtime_hub


class AnswererAccessError(Exception):
    pass


class AnswererUnavailableError(Exception):
    pass


class GenerationCapacityError(Exception):
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
    ) -> ResponseCreation:
        answerer = self.select_answerer(principal, requested_answerer)
        execution_target, artifact_id = self._resolve_runtime(answerer)
        deadline = self._generation_deadline()
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
            )
            await self._add_generation_job(repository, creation, answerer, artifact_id, deadline)
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
        return creation

    async def append(
        self,
        principal: Principal,
        thread_id: UUID,
        content: str,
        requested_answerer: AnswererId | None,
    ) -> ResponseCreation:
        answerer = self.select_answerer(principal, requested_answerer)
        execution_target, artifact_id = self._resolve_runtime(answerer)
        deadline = self._generation_deadline()
        async with self._session_factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            context = await repository.ensure_personal_context(principal)
            await self._reserve_capacity(repository, principal, answerer)
            creation = await repository.append_response(
                principal,
                thread_id,
                context.actor.id,
                content.strip(),
                answerer,
                execution_target=execution_target,
                artifact_id=artifact_id,
                deadline_at=deadline,
            )
            await self._add_generation_job(repository, creation, answerer, artifact_id, deadline)
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
        return creation

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

    async def _add_generation_job(
        self,
        repository: SqlAlchemyThreadRepository,
        creation: ResponseCreation,
        answerer: AnswererDefinition,
        artifact_id: str,
        deadline: datetime,
    ) -> None:
        response = creation.response
        execution = response.execution
        job = GenerationJob.create(
            execution_id=execution.id,
            response_request_id=response.id,
            attempt_id=execution.attempt_id,
            thread_id=creation.thread.id,
            answerer_actor_id=response.target_actor.id,
            model=answerer.runtime_name,
            artifact_id=artifact_id,
            turns=await repository.generation_turns(response.id),
            deadline=deadline,
        )
        await repository.add_generation_outbox(execution.id, job.to_json())

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
            global_limit=self._settings.inference_global_active_limit,
            guest_limit=self._settings.inference_guest_active_limit,
        )
        if not admitted:
            raise GenerationCapacityError

    def _resolve_runtime(self, answerer: AnswererDefinition) -> tuple[str, str]:
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
