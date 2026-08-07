from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from uuid import UUID

from redis.asyncio import Redis
from sodai_contracts.inference import (
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    InferenceCorrelation,
    log_inference_event,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.domain.execution_events import EventDisposition, ExecutionProjection
from app.repositories.threads import SqlAlchemyThreadRepository
from app.services.inference.billing import InferenceBillingService
from app.services.inference.broker import RedisInferenceBroker, StreamBacklog
from app.services.realtime import realtime_hub

logger = logging.getLogger(__name__)


class GenerationCoordinator:
    """Dispatches model jobs and projects every runtime through one state machine."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        broker: RedisInferenceBroker,
        *,
        cancellation_ttl_seconds: int,
        reconciliation_interval_seconds: float = 5,
    ) -> None:
        self._session_factory = session_factory
        self._broker = broker
        self._cancellation_ttl_seconds = cancellation_ttl_seconds
        self._reconciliation_interval_seconds = reconciliation_interval_seconds
        self._deferred_messages: set[str] = set()
        self._recovery_complete = False
        self._tasks: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        if self._tasks:
            return
        self._tasks = {
            asyncio.create_task(self._dispatch_loop(), name="generation-outbox-dispatcher"),
            asyncio.create_task(self._project_loop(), name="generation-event-projector"),
            asyncio.create_task(self._reconcile_loop(), name="generation-reconciler"),
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
                logger.exception("Generation outbox dispatch failed")
                await asyncio.sleep(1)

    async def _dispatch_pending(self) -> int:
        async with self._session_factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            await repository.discard_terminal_outbox()
            cancellations = await repository.pending_cancellation_outbox()
            for message in cancellations:
                try:
                    attempt_id = UUID(message.payload)
                    await self._broker.publish_cancellation(
                        attempt_id,
                        ttl_seconds=self._cancellation_ttl_seconds,
                    )
                except Exception as error:
                    await repository.mark_outbox_failed(message.id, str(error))
                    await session.commit()
                    logger.exception(
                        "Generation cancellation dispatch failed",
                        extra={"execution_id": str(message.execution_id)},
                    )
                    raise
                await repository.mark_outbox_published(message.id)
                logger.info(
                    "Generation cancellation dispatched",
                    extra={
                        "execution_id": str(message.execution_id),
                        "attempt_id": str(attempt_id),
                    },
                )
            pending = await repository.pending_outbox()
            for message in pending:
                job = None
                try:
                    job = GenerationJob.from_json(message.payload)
                    stream_id = await self._broker.publish_job(job)
                except Exception as error:
                    await repository.mark_outbox_failed(message.id, str(error))
                    await session.commit()
                    log_inference_event(
                        logger,
                        logging.ERROR,
                        "generation_job_dispatch_failed",
                        InferenceCorrelation.from_job(job) if job is not None else None,
                        exc_info=True,
                        execution_id=(str(message.execution_id) if job is None else None),
                        error_type=type(error).__name__,
                    )
                    raise
                await repository.mark_outbox_published(message.id)
                log_inference_event(
                    logger,
                    logging.INFO,
                    "generation_job_dispatched",
                    InferenceCorrelation.from_job(job),
                    stream_id=stream_id,
                )
            await session.commit()
            return len(cancellations) + len(pending)

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
                logger.exception("Generation event projection failed")
                await asyncio.sleep(1)

    async def _project(self, message_id: str, payload: str) -> None:
        try:
            event = GenerationEvent.from_json(payload)
        except (TypeError, ValueError):
            logger.exception("Discarding invalid generation event %s", message_id)
            await self._broker.acknowledge_event(message_id)
            self._deferred_messages.discard(message_id)
            return
        try:
            async with self._session_factory() as session:
                result = await SqlAlchemyThreadRepository(session).project_generation_event(
                    event
                )
                if (
                    result.disposition is EventDisposition.APPLY
                    and result.projection is not None
                    and result.projection.status in {"completed", "failed"}
                ):
                    await InferenceBillingService(session).finalize(event.execution_id)
                await session.commit()
        except Exception as error:
            log_inference_event(
                logger,
                logging.ERROR,
                "generation_event_projection_failed",
                InferenceCorrelation.from_event(event),
                exc_info=True,
                stream_id=message_id,
                event_type=event.type.value,
                sequence=event.sequence,
                error_type=type(error).__name__,
            )
            raise
        log_inference_event(
            logger,
            logging.DEBUG
            if event.type in {GenerationEventType.DELTA, GenerationEventType.HEARTBEAT}
            else logging.INFO,
            "generation_event_projected",
            InferenceCorrelation.from_event(event),
            stream_id=message_id,
            event_type=event.type.value,
            sequence=event.sequence,
            disposition=result.disposition.value,
        )
        if result.disposition is EventDisposition.DEFER:
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
                projections = await self._expire_executions()
                delay = 0 if len(projections) == 32 else self._reconciliation_interval_seconds
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._recovery_complete = False
                logger.exception("Generation reconciliation failed")
                await asyncio.sleep(self._reconciliation_interval_seconds)

    async def _expire_executions(self) -> list[ExecutionProjection]:
        async with self._session_factory() as session:
            projections = await SqlAlchemyThreadRepository(session).expire_executions(
                datetime.now(timezone.utc)
                - timedelta(seconds=self._reconciliation_interval_seconds)
            )
            billing = InferenceBillingService(session)
            for projection in projections:
                await billing.finalize(projection.execution_id)
            await session.commit()
        for projection in projections:
            log_inference_event(
                logger,
                logging.WARNING,
                "generation_execution_expired",
                InferenceCorrelation(
                    execution_id=projection.execution_id,
                    response_request_id=projection.response_request_id,
                    attempt_id=projection.attempt_id,
                    thread_id=projection.thread_id,
                ),
                attempt_no=projection.attempt_no,
                error_code=projection.error_code,
            )
            await self._publish_projection(
                projection,
                event_type="response.failed",
                data={
                    "target_actor_id": str(projection.target_actor_id),
                    "error_code": projection.error_code,
                },
            )
        return projections

    async def _publish_realtime(
        self, event: GenerationEvent, projection: ExecutionProjection
    ) -> None:
        if event.type in {
            GenerationEventType.THINKING_DELTA,
            GenerationEventType.HEARTBEAT,
        }:
            return
        if projection.status == "failed":
            event_type = "response.failed"
        else:
            event_type = {
                GenerationEventType.STARTED: "response.started",
                GenerationEventType.PHASE_CHANGED: "response.phase",
                GenerationEventType.DELTA: "response.delta",
                GenerationEventType.COMPLETED: "response.completed",
                GenerationEventType.FAILED: "response.failed",
            }[event.type]
        data: dict[str, str | int | None] = {
            "target_actor_id": str(projection.target_actor_id),
            "result_entry_id": (
                str(projection.result_entry_id) if projection.result_entry_id else None
            ),
        }
        if event_type == "response.started":
            data["resolved_model"] = event.resolved_model
            data["phase"] = event.phase.value if event.phase else None
        elif event_type == "response.phase":
            data["phase"] = event.phase.value if event.phase else None
        elif event_type == "response.delta":
            data.update({"delta": event.delta, "content": projection.content})
        elif event_type == "response.completed":
            data.update({"content": projection.content})
        else:
            data["error_code"] = projection.error_code or event.error_code
        await self._publish_projection(projection, event_type=event_type, data=data)

    @staticmethod
    async def _publish_projection(
        projection: ExecutionProjection,
        *,
        event_type: str,
        data: dict[str, object],
    ) -> None:
        for principal in projection.principals:
            await realtime_hub.publish(
                principal,
                event_type=event_type,
                space_id=projection.space_id,
                thread_id=projection.thread_id,
                thread_revision=projection.thread_revision,
                response_request_id=projection.response_request_id,
                execution_id=projection.execution_id,
                data=data,
            )


def reconciliation_is_safe(backlog: StreamBacklog, deferred_message_count: int) -> bool:
    return backlog.lag == 0 and backlog.pending <= deferred_message_count


def create_generation_coordinator(settings: Settings | None = None) -> GenerationCoordinator:
    settings = settings or get_settings()
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    broker = RedisInferenceBroker(
        redis,
        namespace=settings.inference_keys,
        event_consumer=f"{socket.gethostname()}-{os.getpid()}-api",
        event_claim_idle_ms=settings.inference_event_claim_idle_ms,
    )
    return GenerationCoordinator(
        get_session_factory(),
        broker,
        cancellation_ttl_seconds=settings.inference_job_timeout_seconds + 60,
        reconciliation_interval_seconds=settings.inference_reconciliation_interval_seconds,
    )
