import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sodai_contracts.inference import (
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    GenerationTurn,
    InferenceCorrelation,
    InferenceNamespace,
    InferenceSpeaker,
)

from sodai_inference.config import Settings
from sodai_inference.worker import InferenceWorker

pytestmark = pytest.mark.skipif(
    os.getenv("SODAI_INTEGRATION_TESTS") != "1",
    reason="set SODAI_INTEGRATION_TESTS=1 to exercise local Redis",
)


class StubHina:
    model_name = "hina"
    resolved_model = "hina@integration"
    manifest = SimpleNamespace(artifact_id="integration")


@pytest.mark.asyncio
async def test_event_publish_and_job_ack_are_atomic_in_redis() -> None:
    suffix = uuid4().hex
    settings = Settings(
        model_root=Path("."),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:13204/0"),
        redis_password=os.getenv("REDIS_PASSWORD") or None,
        device="cpu",
        consumer_name="integration-consumer",
        inference_namespace=InferenceNamespace(f"test:{suffix}:inference").prefix,
    )
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    worker = InferenceWorker(settings, redis, StubHina())  # type: ignore[arg-type]
    job = GenerationJob.create(
        execution_id=uuid4(),
        response_request_id=uuid4(),
        attempt_id=uuid4(),
        thread_id=uuid4(),
        answerer_actor_id=uuid4(),
        model="hina",
        artifact_id="integration",
        turns=(GenerationTurn(InferenceSpeaker.PARTNER, "統合テスト"),),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    lock_key = settings.inference_keys.attempt_lock(job.attempt_id)
    progress_key = settings.inference_keys.attempt_progress(job.attempt_id)
    try:
        await redis.set(lock_key, settings.consumer_name, ex=60)
        event = GenerationEvent.create(
            GenerationEventType.STARTED,
            execution_id=job.execution_id,
            attempt_id=job.attempt_id,
            sequence=0,
            thread_id=job.thread_id,
            resolved_model="hina@integration",
        )
        await worker._publish(event, progress_key, InferenceCorrelation.from_job(job))
        assert await redis.xlen(settings.inference_keys.event_stream) == 1
        assert await redis.get(progress_key) is not None

        await worker._ensure_group()
        message_id = await redis.xadd(worker._job_stream, {"payload": job.to_json()})
        await redis.xreadgroup(
            groupname=settings.inference_keys.worker_group,
            consumername=settings.consumer_name,
            streams={worker._job_stream: ">"},
            count=1,
        )
        await worker._ack(message_id)
        assert await redis.xlen(worker._job_stream) == 0
    finally:
        await redis.delete(
            settings.inference_keys.event_stream,
            worker._job_stream,
            lock_key,
            progress_key,
        )
        await redis.aclose()
