from __future__ import annotations

import asyncio
import logging
import os
import socket
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sodai_contracts.inference import GenerationEvent, GenerationEventType
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.domain.inference import InferenceEventDisposition, InferenceProjection
from app.repositories.conversations import SqlAlchemyConversationRepository
from app.services.inference.broker import RedisInferenceBroker, StreamBacklog
from app.services.realtime import realtime_hub

logger = logging.getLogger(__name__)


class InferenceCoordinator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: RedisInferenceBroker,
        *,
        reconciliation_interval_seconds: float = 5,
    ) -> None:
        self._session_factory = session_factory
        self._broker = broker
        self._reconciliation_interval_seconds = reconciliation_interval_seconds
        self._deferred_messages: set[str] = set()
        self._recovery_complete = False
        self._tasks: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        if self._tasks:
            return
        self._tasks = {
            asyncio.create_task(self._dispatch_loop(), name="inference-outbox-dispatcher"),
            asyncio.create_task(self._project_loop(), name="inference-event-projector"),
            asyncio.create_task(self._reconcile_loop(), name="inference-run-reconciler"),
        }

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await self._broker.close()

    async def _dispatch_loop(self) -> None:
        while True:
            try:
                dispatched = await self._dispatch_pending()
                await asyncio.sleep(0 if dispatched else 0.25)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Inference outbox dispatch failed")
                await asyncio.sleep(1)

    async def _dispatch_pending(self) -> int:
        async with self._session_factory() as session:
            repository = SqlAlchemyConversationRepository(session)
            pending = await repository.pending_inference_outbox()
            for message in pending:
                try:
                    await self._broker.publish_job(message.payload)
                except Exception as error:
                    await repository.mark_outbox_failed(message.id, str(error))
                    await session.commit()
                    raise
                await repository.mark_outbox_published(message.id)
            await session.commit()
            return len(pending)

    async def _project_loop(self) -> None:
        while True:
            try:
                await self._broker.ensure_event_group()
                for message in await self._broker.read_events():
                    await self._project(message.id, message.payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._recovery_complete = False
                logger.exception("Inference event projection failed")
                await asyncio.sleep(1)

    async def _project(self, message_id: str, payload: str) -> None:
        try:
            event = GenerationEvent.from_json(payload)
        except (TypeError, ValueError):
            logger.exception("Discarding invalid inference event %s", message_id)
            await self._broker.acknowledge_event(message_id)
            self._deferred_messages.discard(message_id)
            return

        async with self._session_factory() as session:
            result = await SqlAlchemyConversationRepository(session).project_inference_event(event)
            await session.commit()
        if result.disposition is InferenceEventDisposition.DEFER:
            self._deferred_messages.add(message_id)
            return
        if result.projection is not None:
            await self._publish_realtime(event, result.projection)
        await self._broker.acknowledge_event(message_id)
        self._deferred_messages.discard(message_id)

    async def _reconcile_loop(self) -> None:
        while True:
            try:
                if not self._recovery_complete:
                    backlog = await self._broker.event_backlog()
                    if not reconciliation_is_safe(backlog, len(self._deferred_messages)):
                        await asyncio.sleep(0.25)
                        continue
                    self._recovery_complete = True
                projections = await self._expire_runs()
                delay = 0 if len(projections) == 32 else self._reconciliation_interval_seconds
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._recovery_complete = False
                logger.exception("Inference run reconciliation failed")
                await asyncio.sleep(self._reconciliation_interval_seconds)

    async def _expire_runs(self) -> list[InferenceProjection]:
        async with self._session_factory() as session:
            projections = await SqlAlchemyConversationRepository(session).expire_inference_runs(
                datetime.now(timezone.utc)
                - timedelta(seconds=self._reconciliation_interval_seconds)
            )
            await session.commit()
        for projection in projections:
            await realtime_hub.publish(
                projection.principal,
                "response.failed",
                projection.conversation_id,
                projection.run_id,
                {
                    "message_id": str(projection.output_message_id),
                    "error_code": "inference_timeout",
                },
            )
        return projections

    @staticmethod
    async def _publish_realtime(event, projection) -> None:
        message_id = str(projection.output_message_id)
        if event.type is GenerationEventType.HEARTBEAT:
            return
        event_type = {
            GenerationEventType.STARTED: "response.started",
            GenerationEventType.DELTA: "response.delta",
            GenerationEventType.COMPLETED: "response.completed",
            GenerationEventType.FAILED: "response.failed",
        }[event.type]
        data = {"message_id": message_id}
        if event.type is GenerationEventType.STARTED:
            data["resolved_model"] = event.resolved_model
        elif event.type is GenerationEventType.DELTA:
            data.update({"delta": event.delta, "content": projection.content})
        elif event.type is GenerationEventType.COMPLETED:
            data.update(
                {
                    "content": projection.content,
                    "finish_reason": event.finish_reason.value if event.finish_reason else None,
                }
            )
        await realtime_hub.publish(
            projection.principal,
            event_type,
            projection.conversation_id,
            projection.run_id,
            data,
        )


def reconciliation_is_safe(backlog: StreamBacklog, deferred_message_count: int) -> bool:
    return backlog.lag == 0 and backlog.pending <= deferred_message_count


def create_inference_coordinator(settings: Settings | None = None) -> InferenceCoordinator:
    settings = settings or get_settings()
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    broker = RedisInferenceBroker(
        redis,
        job_stream=settings.inference_job_stream,
        event_stream=settings.inference_event_stream,
        event_group=settings.inference_event_group,
        event_consumer=f"{socket.gethostname()}-{os.getpid()}-api",
        event_claim_idle_ms=settings.inference_event_claim_idle_ms,
    )
    return InferenceCoordinator(
        get_session_factory(),
        broker,
        reconciliation_interval_seconds=settings.inference_reconciliation_interval_seconds,
    )


_coordinator: InferenceCoordinator | None = None


def get_inference_coordinator() -> InferenceCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = create_inference_coordinator()
    return _coordinator


async def reset_inference_coordinator() -> None:
    global _coordinator
    if _coordinator is not None:
        with suppress(Exception):
            await _coordinator.stop()
    _coordinator = None
