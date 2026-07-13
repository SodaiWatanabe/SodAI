from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    InferenceCorrelation,
    log_inference_event,
)

from sodai_inference.config import Settings
from sodai_inference.deployment import resolve_hina_artifact
from sodai_inference.models.hina import HinaEngine

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


class InferenceWorker:
    def __init__(self, settings: Settings, redis: Redis, hina: HinaEngine) -> None:
        self._settings = settings
        self._redis = redis
        self._hina = hina
        self._namespace = settings.inference_keys
        self._job_stream = self._namespace.job_stream_for(
            hina.model_name, hina.manifest.artifact_id
        )
        self._job_claim_cursor = "0-0"

    async def run(self) -> None:
        await self._ensure_group()
        await self._announce_readiness()
        logger.info("Hina worker ready with %s", self._hina.resolved_model)
        readiness_task = asyncio.create_task(
            self._readiness_loop(), name="hina-readiness-lease"
        )
        try:
            while True:
                messages = await self._next_jobs()
                for message_id, fields in messages:
                    await self._process(message_id, fields)
        finally:
            readiness_task.cancel()
            await asyncio.gather(readiness_task, return_exceptions=True)

    async def _readiness_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(10)
                await self._announce_readiness()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Hina readiness lease refresh failed")
                await asyncio.sleep(1)

    async def _announce_readiness(self) -> None:
        await self._redis.set(
            self._namespace.worker_readiness(
                self._hina.model_name, self._hina.manifest.artifact_id
            ),
            self._settings.consumer_name,
            ex=30,
        )

    async def _next_jobs(self) -> list[tuple[str, dict[str, Any]]]:
        claimed = await self._redis.xautoclaim(
            self._job_stream,
            self._namespace.worker_group,
            self._settings.consumer_name,
            min_idle_time=self._settings.job_claim_idle_ms,
            start_id=self._job_claim_cursor,
            count=1,
        )
        if claimed:
            self._job_claim_cursor = claimed[0]
        if len(claimed) > 1 and claimed[1]:
            return claimed[1]
        streams = await self._redis.xreadgroup(
            groupname=self._namespace.worker_group,
            consumername=self._settings.consumer_name,
            streams={self._job_stream: ">"},
            count=1,
            block=5_000,
        )
        return streams[0][1] if streams else []

    async def _ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                self._job_stream,
                self._namespace.worker_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def _process(self, message_id: str, fields: dict[str, Any]) -> None:
        payload = fields.get("payload")
        if not isinstance(payload, str):
            logger.error("Discarding inference job %s without payload", message_id)
            await self._ack(message_id)
            return

        try:
            job = GenerationJob.from_json(payload)
        except (TypeError, ValueError):
            logger.exception("Discarding invalid inference job %s", message_id)
            await self._ack(message_id)
            return
        correlation = InferenceCorrelation.from_job(job)
        if (
            job.model != self._hina.model_name
            or job.artifact_id != self._hina.manifest.artifact_id
        ):
            log_inference_event(
                logger,
                logging.ERROR,
                "generation_job_misrouted",
                correlation,
                stream_id=message_id,
            )
            await self._ack(message_id)
            return
        lock_key = self._namespace.attempt_lock(job.attempt_id)
        progress_key = self._namespace.attempt_progress(job.attempt_id)
        acquired = await self._redis.set(
            lock_key,
            self._settings.consumer_name,
            ex=self._settings.run_lock_seconds,
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
            if not progress.terminal:
                await self._generate(job, resume_after_sequence=progress.sequence)
            marked_done = await self._redis.eval(
                COMPARE_AND_SET_SCRIPT,
                1,
                lock_key,
                self._settings.consumer_name,
                "done",
                86_400,
            )
            if marked_done != 1:
                raise RuntimeError("inference attempt lock was lost before completion")
            await self._ack(message_id)
        except asyncio.CancelledError:
            await self._redis.eval(
                COMPARE_AND_DELETE_SCRIPT,
                1,
                lock_key,
                self._settings.consumer_name,
            )
            raise
        except Exception as error:
            log_inference_event(
                logger,
                logging.ERROR,
                "generation_job_transport_failed",
                correlation,
                exc_info=True,
                stream_id=message_id,
                error_type=type(error).__name__,
            )
            await self._redis.eval(
                COMPARE_AND_DELETE_SCRIPT,
                1,
                lock_key,
                self._settings.consumer_name,
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
            await emit(self._failed_event(job, sequence))
            return

        try:
            prompt_ids = self._hina.build_prompt(job)
        except Exception as error:
            log_inference_event(
                logger,
                logging.ERROR,
                "generation_prompt_failed",
                correlation,
                exc_info=True,
                error_type=type(error).__name__,
            )
            await emit(self._failed_event(job, sequence))
            return

        await emit(
            GenerationEvent.create(
                GenerationEventType.STARTED,
                execution_id=job.execution_id,
                attempt_id=job.attempt_id,
                sequence=sequence,
                thread_id=job.thread_id,
                resolved_model=self._hina.resolved_model,
                input_tokens=len(prompt_ids),
            )
        )
        buffered_delta = ""
        buffered_tokens = 0
        steps = iter(self._hina.generate(prompt_ids, job))
        while True:
            try:
                step = next(steps)
            except StopIteration:
                log_inference_event(
                    logger,
                    logging.ERROR,
                    "generation_ended_without_terminal_step",
                    correlation,
                )
                await emit(self._failed_event(job, sequence + 1))
                return
            except Exception as error:
                log_inference_event(
                    logger,
                    logging.ERROR,
                    "generation_model_failed",
                    correlation,
                    exc_info=True,
                    error_type=type(error).__name__,
                )
                await emit(self._failed_event(job, sequence + 1))
                return

            if step.finish_reason is None:
                buffered_delta += step.delta
                buffered_tokens = step.output_tokens
                if len(buffered_delta) < 4:
                    continue
                sequence += 1
                await emit(
                    GenerationEvent.create(
                        GenerationEventType.DELTA,
                        execution_id=job.execution_id,
                        attempt_id=job.attempt_id,
                        sequence=sequence,
                        thread_id=job.thread_id,
                        delta=buffered_delta,
                        output_tokens=buffered_tokens,
                    )
                )
                buffered_delta = ""
                continue

            if buffered_delta:
                sequence += 1
                await emit(
                    GenerationEvent.create(
                        GenerationEventType.DELTA,
                        execution_id=job.execution_id,
                        attempt_id=job.attempt_id,
                        sequence=sequence,
                        thread_id=job.thread_id,
                        delta=buffered_delta,
                        output_tokens=buffered_tokens,
                    )
                )
            sequence += 1
            await emit(
                GenerationEvent.create(
                    GenerationEventType.COMPLETED,
                    execution_id=job.execution_id,
                    attempt_id=job.attempt_id,
                    sequence=sequence,
                    thread_id=job.thread_id,
                    content=step.content,
                    output_tokens=step.output_tokens,
                    finish_reason=step.finish_reason,
                )
            )
            return

    @staticmethod
    def _failed_event(job: GenerationJob, sequence: int) -> GenerationEvent:
        return GenerationEvent.create(
            GenerationEventType.FAILED,
            execution_id=job.execution_id,
            attempt_id=job.attempt_id,
            sequence=sequence,
            thread_id=job.thread_id,
            finish_reason=FinishReason.ERROR,
            error_code="hina_generation_failed",
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
            self._namespace.event_stream,
            progress_key,
            progress_key.removesuffix(":progress"),
            self._namespace.worker_readiness(
                self._hina.model_name, self._hina.manifest.artifact_id
            ),
            event.to_json(),
            progress,
            self._settings.consumer_name,
            self._settings.run_lock_seconds,
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
            raise ValueError("inference attempt progress is invalid")
        return AttemptProgress(sequence=sequence, terminal=terminal)

    async def _ack(self, message_id: str) -> None:
        await self._redis.eval(
            ACK_AND_DELETE_SCRIPT,
            1,
            self._job_stream,
            self._namespace.worker_group,
            message_id,
        )


async def run_worker() -> None:
    settings = Settings.from_env()
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    artifact_path = resolve_hina_artifact(settings.model_root, settings.artifact_id)
    hina = HinaEngine.load(artifact_path, settings.device)
    worker = InferenceWorker(settings, redis, hina)
    try:
        await worker.run()
    finally:
        await redis.aclose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
