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
    PrincipalKind,
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
        self, principal: ConversationPrincipal, content: str, model: str
    ) -> ConversationCreation:
        resolved = self.resolve_model(principal, model)
        async with self._session_factory() as session:
            creation = await SqlAlchemyConversationRepository(session).create(
                principal, content.strip(), model, resolved
            )
            await session.commit()
        await realtime_hub.publish(
            principal,
            "conversation.created",
            creation.conversation.id,
            creation.run.id,
            {"title": creation.conversation.title, "model": model},
        )
        self._start_generation(principal, creation.run.id, content.strip())
        return creation

    async def list(self, principal: ConversationPrincipal) -> list[ConversationSummary]:
        async with self._session_factory() as session:
            return await SqlAlchemyConversationRepository(session).list(principal)

    async def get(self, principal: ConversationPrincipal, conversation_id: UUID) -> Conversation:
        async with self._session_factory() as session:
            return await SqlAlchemyConversationRepository(session).get(principal, conversation_id)

    async def add_turn(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        content: str,
        model: str,
    ) -> ConversationCreation:
        resolved = self.resolve_model(principal, model)
        async with self._session_factory() as session:
            creation = await SqlAlchemyConversationRepository(session).append_turn(
                principal, conversation_id, content.strip(), model, resolved
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
            },
        )
        self._start_generation(principal, creation.run.id, content.strip())
        return creation

    @staticmethod
    def available_models(principal: ConversationPrincipal) -> list[dict[str, str]]:
        models = [
            {
                "id": "archive",
                "name": "Archive",
                "description": "SodAIのアーカイブモデル。現在は疑似応答です。",
            }
        ]
        if principal.kind is PrincipalKind.USER:
            models.insert(
                0,
                {
                    "id": "flagship",
                    "name": "Flagship",
                    "description": "ログインユーザー向けモデル。現在は疑似応答です。",
                },
            )
        return models

    @staticmethod
    def resolve_model(principal: ConversationPrincipal, requested: str) -> str:
        if requested == "flagship" and principal.kind is not PrincipalKind.USER:
            raise ModelAccessError
        if requested not in {"archive", "flagship"}:
            raise ModelAccessError
        return f"pseudo-sodai-{requested}-v1"

    def _start_generation(
        self, principal: ConversationPrincipal, run_id: UUID, content: str
    ) -> None:
        task = asyncio.create_task(self._generate(principal, run_id, content))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _generate(self, principal: ConversationPrincipal, run_id: UUID, content: str) -> None:
        generated = ""
        conversation_id: UUID | None = None
        output_message_id: UUID | None = None
        try:
            async with self._session_factory() as session:
                run, _ = await SqlAlchemyConversationRepository(session).begin_run(run_id)
                await session.commit()
                conversation_id = run.conversation_id
                output_message_id = run.output_message_id
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
            if conversation_id is not None:
                await realtime_hub.publish(
                    principal,
                    "response.failed",
                    conversation_id,
                    run_id,
                    {"message_id": str(output_message_id) if output_message_id else None},
                )

    async def shutdown(self) -> None:
        if not self._tasks:
            return
        for task in tuple(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def recover_interrupted_runs(self) -> int:
        """Fail work orphaned by a previous single-process API instance."""

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
