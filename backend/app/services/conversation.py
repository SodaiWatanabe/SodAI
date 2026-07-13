from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session_factory
from app.domain.conversations import (
    Conversation,
    ConversationCreation,
    ConversationPrincipal,
    ConversationSummary,
    InferenceRun,
    PrincipalKind,
)
from app.domain.model_catalog import (
    AvailableModel,
    ModelAudience,
    ModelDefinition,
    ModelId,
    get_default_model,
    get_model_definition,
    list_available_models,
)
from app.repositories.conversations import SqlAlchemyConversationRepository
from app.services.pseudo_inference import PseudoSodAI
from app.services.realtime import realtime_hub

logger = logging.getLogger(__name__)


class ModelAccessError(Exception):
    pass


class ConversationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: PseudoSodAI,
    ) -> None:
        self._session_factory = session_factory
        self._provider = provider
        self._tasks: set[asyncio.Task[None]] = set()

    async def create(
        self, principal: ConversationPrincipal, content: str, model: ModelId | None
    ) -> ConversationCreation:
        selected = self.select_model(principal, model)
        async with self._session_factory() as session:
            creation = await SqlAlchemyConversationRepository(session).create(
                principal, content.strip(), selected.id, selected.runtime_id
            )
            await session.commit()
        await realtime_hub.publish(
            principal,
            "conversation.created",
            creation.conversation.id,
            creation.run.id,
            {
                "title": creation.conversation.title,
                "model": selected.id.value,
                "created_at": creation.conversation.created_at.isoformat(),
                "updated_at": creation.conversation.updated_at.isoformat(),
                "last_activity_at": creation.conversation.last_activity_at.isoformat(),
            },
        )
        return creation

    async def list(self, principal: ConversationPrincipal) -> list[ConversationSummary]:
        async with self._session_factory() as session:
            return await SqlAlchemyConversationRepository(session).list(principal)

    async def get(self, principal: ConversationPrincipal, conversation_id: UUID) -> Conversation:
        async with self._session_factory() as session:
            return await SqlAlchemyConversationRepository(session).get(principal, conversation_id)

    async def update_title(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        title: str,
    ) -> ConversationSummary:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Conversation title cannot be blank")
        async with self._session_factory() as session:
            conversation = await SqlAlchemyConversationRepository(session).update_title(
                principal, conversation_id, normalized_title
            )
            await session.commit()
        await realtime_hub.publish(
            principal,
            "conversation.updated",
            conversation_id,
            None,
            {
                "title": conversation.title,
                "updated_at": conversation.updated_at.isoformat(),
            },
        )
        return conversation

    async def archive(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
    ) -> None:
        async with self._session_factory() as session:
            await SqlAlchemyConversationRepository(session).archive(principal, conversation_id)
            await session.commit()
        await realtime_hub.publish(
            principal,
            "conversation.archived",
            conversation_id,
            None,
            {},
        )

    async def add_turn(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        content: str,
        model: ModelId | None,
    ) -> ConversationCreation:
        selected = self.select_model(principal, model)
        async with self._session_factory() as session:
            creation = await SqlAlchemyConversationRepository(session).append_turn(
                principal,
                conversation_id,
                content.strip(),
                selected.id,
                selected.runtime_id,
            )
            await session.commit()
        await realtime_hub.publish(
            principal,
            "message.created",
            conversation_id,
            creation.run.id,
            {
                "input_message_id": str(creation.run.input_message_id),
                "output_message_id": str(creation.run.output_message_id),
                "model": selected.id.value,
                "last_activity_at": creation.conversation.last_activity_at.isoformat(),
            },
        )
        return creation

    async def start_run(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        run_id: UUID,
    ) -> InferenceRun:
        async with self._session_factory() as session:
            run, content = await SqlAlchemyConversationRepository(session).claim_queued_run(
                principal,
                conversation_id,
                run_id,
            )
            await session.commit()
        if content is not None:
            self._start_generation(principal, run, content)
        return run

    @staticmethod
    def available_models(principal: ConversationPrincipal) -> list[AvailableModel]:
        return list_available_models(ConversationService._model_audience(principal))

    @staticmethod
    def select_model(
        principal: ConversationPrincipal, requested: ModelId | None
    ) -> ModelDefinition:
        audience = ConversationService._model_audience(principal)
        model = (
            get_model_definition(requested)
            if requested is not None
            else get_default_model(audience)
        )
        if model is None or audience not in model.audiences:
            raise ModelAccessError
        return model

    @staticmethod
    def _model_audience(principal: ConversationPrincipal) -> ModelAudience:
        if principal.kind is PrincipalKind.USER:
            return ModelAudience.AUTHENTICATED
        return ModelAudience.GUEST

    def _start_generation(
        self, principal: ConversationPrincipal, run: InferenceRun, content: str
    ) -> None:
        task = asyncio.create_task(self._generate(principal, run, content))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _generate(
        self,
        principal: ConversationPrincipal,
        run: InferenceRun,
        content: str,
    ) -> None:
        generated = ""
        run_id = run.id
        conversation_id = run.conversation_id
        output_message_id = run.output_message_id
        try:
            await realtime_hub.publish(
                principal,
                "response.started",
                conversation_id,
                run_id,
                {"message_id": str(output_message_id)},
            )
            chunk_count = 0
            async for delta in self._provider.stream(content):
                generated += delta
                chunk_count += 1
                if chunk_count % 8 == 0:
                    async with self._session_factory() as session:
                        await SqlAlchemyConversationRepository(session).save_delta(
                            run_id, generated
                        )
                        await session.commit()
                await realtime_hub.publish(
                    principal,
                    "response.delta",
                    conversation_id,
                    run_id,
                    {
                        "message_id": str(output_message_id),
                        "delta": delta,
                        "content": generated,
                    },
                )
            async with self._session_factory() as session:
                await SqlAlchemyConversationRepository(session).complete_run(run_id, generated)
                await session.commit()
            await realtime_hub.publish(
                principal,
                "response.completed",
                conversation_id,
                run_id,
                {"message_id": str(output_message_id), "content": generated},
            )
        except asyncio.CancelledError:
            async with self._session_factory() as session:
                await SqlAlchemyConversationRepository(session).fail_run(run_id)
                await session.commit()
            raise
        except Exception:
            logger.exception("Pseudo inference run %s failed", run_id)
            async with self._session_factory() as session:
                await SqlAlchemyConversationRepository(session).fail_run(run_id)
                await session.commit()
            await realtime_hub.publish(
                principal,
                "response.failed",
                conversation_id,
                run_id,
                {"message_id": str(output_message_id)},
            )

    async def shutdown(self) -> None:
        if not self._tasks:
            return
        for task in tuple(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def recover_interrupted_runs(self) -> int:
        """Fail running work orphaned by a previous single-process API instance."""

        async with self._session_factory() as session:
            count = await SqlAlchemyConversationRepository(session).fail_interrupted_runs()
            await session.commit()
        if count:
            logger.warning("Marked %d interrupted inference runs as failed", count)
        return count


@lru_cache
def get_conversation_service_singleton() -> ConversationService:
    return ConversationService(get_session_factory(), PseudoSodAI())


def get_conversation_service() -> ConversationService:
    return get_conversation_service_singleton()
