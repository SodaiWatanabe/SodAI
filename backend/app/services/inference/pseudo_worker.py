from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sodai_contracts.inference import (
    INFERENCE_ATTEMPT_LOCK_SECONDS,
    INFERENCE_JOB_CLAIM_IDLE_MS,
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    InferenceCorrelation,
    InferenceNamespace,
    log_inference_event,
)

from app.core.config import Settings, get_settings
from app.services.inference.asuka import (
    ASUKA_PSEUDO_ARTIFACT_ID,
    ASUKA_PSEUDO_RESOLVED_MODEL,
    AsukaPseudoGenerator,
)

logger = logging.getLogger(__name__)

PUBLISH_EVENT_SCRIPT = """
if redis.call('GET', KEYS[3]) ~= ARGV[3] then
    return redis.error_reply('ATTEMPT_LOCK_LOST')
end
local event_id = redis.call(
    'XADD', KEYS[1], 'MAXLEN', '~', 100000, '*', 'payload', ARGV[1]
)
redis.call('SET', KEYS[2], ARGV[2], 'EX', 86400)
redis.call('EXPIRE', KEYS[3], ARGV[4])
redis.call('SET', KEYS[4], ARGV[3], 'EX', 30)
return event_id
"""

COMPARE_AND_SET_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
    return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""

COMPARE_AND_DELETE_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
    return 0
end
return redis.call('DEL', KEYS[1])
"""

ACK_AND_DELETE_SCRIPT = """
local acknowledged = redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('XDEL', KEYS[1], ARGV[2])
return acknowledged
"""


@dataclass(frozen=True, slots=True)
class AttemptProgress:
    sequence: int
    terminal: bool


class PseudoGenerationWorker:
    """Consumes Asuka jobs and emits the same events as an external model worker."""

    model = "asuka-1"
    artifact_id = ASUKA_PSEUDO_ARTIFACT_ID

    def __init__(
        self,
        redis: Redis,
        generator: AsukaPseudoGenerator,
        *,
        namespace: InferenceNamespace,
        consumer_name: str,
        job_claim_idle_ms: int = INFERENCE_JOB_CLAIM_IDLE_MS,
        run_lock_seconds: int = INFERENCE_ATTEMPT_LOCK_SECONDS,
    ) -> None:
        self._redis = redis
        self._generator = generator
        self._namespace = namespace
        self._job_stream = namespace.job_stream_for(self.model, self.artifact_id)
        self._event_stream = namespace.event_stream
        self._worker_group = namespace.worker_group
        self._consumer_name = consumer_name
        self._job_claim_idle_ms = job_claim_idle_ms
        self._run_lock_seconds = run_lock_seconds
        self._claim_cursor = "0-0"
        self._task: asyncio.Task[None] | None = None
        self._readiness_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="asuka-pseudo-worker")
            self._readiness_task = asyncio.create_task(
                self._readiness_loop(), name="asuka-readiness-lease"
            )

    async def stop(self) -> None:
        tasks = [task for task in (self._task, self._readiness_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._task = None
        self._readiness_task = None
        await self._redis.aclose()

    async def _run(self) -> None:
        while True:
            try:
                await self._ensure_group()
                for message_id, fields in await self._next_jobs():
                    await self._process(message_id, fields)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Asuka pseudo worker failed")
                await asyncio.sleep(1)

    async def _readiness_loop(self) -> None:
        while True:
            try:
                await self._announce_readiness()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Asuka readiness lease refresh failed")
                await asyncio.sleep(1)

    async def _announce_readiness(self) -> None:
        await self._redis.set(
            self._namespace.worker_readiness(self.model, self.artifact_id),
            self._consumer_name,
            ex=30,
        )

    async def _next_jobs(self) -> list[tuple[str, dict[str, Any]]]:
        claimed = await self._redis.xautoclaim(
            self._job_stream,
            self._worker_group,
            self._consumer_name,
            min_idle_time=self._job_claim_idle_ms,
            start_id=self._claim_cursor,
            count=1,
        )
        if claimed:
            self._claim_cursor = claimed[0]
        if len(claimed) > 1 and claimed[1]:
            return claimed[1]
        streams = await self._redis.xreadgroup(
            groupname=self._worker_group,
            consumername=self._consumer_name,
            streams={self._job_stream: ">"},
            count=1,
            block=250,
        )
        return streams[0][1] if streams else []

    async def _ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                self._job_stream, self._worker_group, id="0-0", mkstream=True
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def _process(self, message_id: str, fields: dict[str, Any]) -> None:
        payload = fields.get("payload")
        if not isinstance(payload, str):
            await self._ack(message_id)
            return
        try:
            job = GenerationJob.from_json(payload)
        except (TypeError, ValueError):
            logger.exception("Discarding invalid Asuka job %s", message_id)
            await self._ack(message_id)
            return
        if job.model != self.model or job.artifact_id != self.artifact_id:
            log_inference_event(
                logger,
                logging.ERROR,
                "generation_job_misrouted",
                InferenceCorrelation.from_job(job),
                stream_id=message_id,
            )
            await self._ack(message_id)
            return

        correlation = InferenceCorrelation.from_job(job)
        lock_key = self._namespace.attempt_lock(job.attempt_id)
        progress_key = self._namespace.attempt_progress(job.attempt_id)
        acquired = await self._redis.set(
            lock_key,
            self._consumer_name,
            ex=self._run_lock_seconds,
            nx=True,
        )
        if not acquired:
            state = await self._redis.get(lock_key)
            if state == "done":
                await self._ack(message_id)
            log_inference_event(
                logger,
                logging.DEBUG,
                "generation_job_lock_unavailable",
                correlation,
                stream_id=message_id,
                lock_state=state,
            )
            return
        try:
            log_inference_event(
                logger,
                logging.INFO,
                "generation_job_claimed",
                correlation,
                stream_id=message_id,
            )
            progress = await self._read_progress(progress_key)
            if not progress.terminal and not await self._cancel_requested(job):
                await self._generate(job, resume_after_sequence=progress.sequence)
            marked_done = await self._redis.eval(
                COMPARE_AND_SET_SCRIPT,
                1,
                lock_key,
                self._consumer_name,
                "done",
                86_400,
            )
            if marked_done != 1:
                raise RuntimeError("Asuka attempt lock was lost before completion")
            await self._ack(message_id)
        except asyncio.CancelledError:
            await self._release_lock(lock_key)
            raise
        except Exception as error:
            await self._release_lock(lock_key)
            log_inference_event(
                logger,
                logging.ERROR,
                "generation_job_transport_failed",
                correlation,
                exc_info=True,
                stream_id=message_id,
                error_type=type(error).__name__,
            )

    async def _generate(self, job: GenerationJob, *, resume_after_sequence: int = -1) -> None:
        sequence = 0
        progress_key = self._namespace.attempt_progress(job.attempt_id)
        correlation = InferenceCorrelation.from_job(job)

        async def emit(event: GenerationEvent) -> None:
            if event.sequence <= resume_after_sequence:
                return
            await self._publish(event, progress_key, correlation)

        if resume_after_sequence < 0 and datetime.now(timezone.utc) >= job.deadline:
            await emit(self._failed(job, sequence, "generation_timeout"))
            return
        if await self._cancel_requested(job):
            return
        await emit(
            GenerationEvent.create(
                GenerationEventType.STARTED,
                execution_id=job.execution_id,
                attempt_id=job.attempt_id,
                sequence=sequence,
                thread_id=job.thread_id,
                resolved_model=ASUKA_PSEUDO_RESOLVED_MODEL,
            )
        )
        generated = ""
        try:
            async for delta in self._generator.stream(job.turns[-1].content):
                if await self._cancel_requested(job):
                    log_inference_event(
                        logger,
                        logging.INFO,
                        "generation_cancelled",
                        correlation,
                        sequence=sequence,
                    )
                    return
                generated += delta
                sequence += 1
                await emit(
                    GenerationEvent.create(
                        GenerationEventType.DELTA,
                        execution_id=job.execution_id,
                        attempt_id=job.attempt_id,
                        sequence=sequence,
                        thread_id=job.thread_id,
                        delta=delta,
                    )
                )
        except Exception as error:
            log_inference_event(
                logger,
                logging.ERROR,
                "generation_model_failed",
                correlation,
                exc_info=True,
                error_type=type(error).__name__,
            )
            await emit(self._failed(job, sequence + 1, "asuka_generation_failed"))
            return
        if await self._cancel_requested(job):
            log_inference_event(
                logger,
                logging.INFO,
                "generation_cancelled",
                correlation,
                sequence=sequence,
            )
            return
        sequence += 1
        await emit(
            GenerationEvent.create(
                GenerationEventType.COMPLETED,
                execution_id=job.execution_id,
                attempt_id=job.attempt_id,
                sequence=sequence,
                thread_id=job.thread_id,
                content=generated,
                finish_reason=FinishReason.STOP,
            )
        )

    async def _cancel_requested(self, job: GenerationJob) -> bool:
        return bool(
            await self._redis.exists(
                self._namespace.attempt_cancellation(job.attempt_id)
            )
        )

    @staticmethod
    def _failed(job: GenerationJob, sequence: int, error_code: str) -> GenerationEvent:
        return GenerationEvent.create(
            GenerationEventType.FAILED,
            execution_id=job.execution_id,
            attempt_id=job.attempt_id,
            sequence=sequence,
            thread_id=job.thread_id,
            finish_reason=FinishReason.ERROR,
            error_code=error_code,
        )

    async def _publish(
        self,
        event: GenerationEvent,
        progress_key: str,
        correlation: InferenceCorrelation,
    ) -> None:
        progress = json.dumps(
            {
                "sequence": event.sequence,
                "terminal": event.type
                in {GenerationEventType.COMPLETED, GenerationEventType.FAILED},
            },
            separators=(",", ":"),
        )
        await self._redis.eval(
            PUBLISH_EVENT_SCRIPT,
            4,
            self._event_stream,
            progress_key,
            progress_key.removesuffix(":progress"),
            self._namespace.worker_readiness(self.model, self.artifact_id),
            event.to_json(),
            progress,
            self._consumer_name,
            self._run_lock_seconds,
        )
        log_inference_event(
            logger,
            logging.DEBUG
            if event.type in {GenerationEventType.DELTA, GenerationEventType.HEARTBEAT}
            else logging.INFO,
            "generation_event_published",
            correlation,
            event_type=event.type.value,
            sequence=event.sequence,
            output_tokens=event.output_tokens,
            error_code=event.error_code,
        )

    async def _read_progress(self, progress_key: str) -> AttemptProgress:
        payload = await self._redis.get(progress_key)
        if payload is None:
            return AttemptProgress(sequence=-1, terminal=False)
        value = json.loads(payload)
        sequence = value.get("sequence")
        terminal = value.get("terminal")
        if not isinstance(sequence, int) or sequence < 0 or not isinstance(terminal, bool):
            raise ValueError("Asuka attempt progress is invalid")
        return AttemptProgress(sequence=sequence, terminal=terminal)

    async def _release_lock(self, lock_key: str) -> None:
        await self._redis.eval(
            COMPARE_AND_DELETE_SCRIPT,
            1,
            lock_key,
            self._consumer_name,
        )

    async def _ack(self, message_id: str) -> None:
        await self._redis.eval(
            ACK_AND_DELETE_SCRIPT,
            1,
            self._job_stream,
            self._worker_group,
            message_id,
        )


def create_pseudo_generation_worker(
    settings: Settings | None = None,
) -> PseudoGenerationWorker:
    settings = settings or get_settings()
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    return PseudoGenerationWorker(
        redis,
        AsukaPseudoGenerator(),
        namespace=settings.inference_keys,
        consumer_name=f"{socket.gethostname()}-{os.getpid()}-asuka",
    )
