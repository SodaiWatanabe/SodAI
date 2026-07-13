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
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        redis_password=os.getenv("REDIS_PASSWORD") or None,
        device="cpu",
        consumer_name="integration-consumer",
        job_stream=f"test:jobs:{suffix}",
        event_stream=f"test:events:{suffix}",
        worker_group=f"test:workers:{suffix}",
    )
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    worker = InferenceWorker(settings, redis, StubHina())  # type: ignore[arg-type]
    job = GenerationJob.create(
        run_id=uuid4(),
        attempt_id=uuid4(),
        conversation_id=uuid4(),
        model="hina",
        artifact_id="integration",
        turns=(GenerationTurn(InferenceSpeaker.PARTNER, "統合テスト"),),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    lock_key = f"sodai:inference:attempt:{job.attempt_id}"
    progress_key = f"{lock_key}:progress"
    try:
        await redis.set(lock_key, settings.consumer_name, ex=60)
        event = GenerationEvent.create(
            GenerationEventType.STARTED,
            run_id=job.run_id,
            attempt_id=job.attempt_id,
            sequence=0,
            conversation_id=job.conversation_id,
            resolved_model="hina@integration",
        )
        await worker._publish(event, progress_key)
        assert await redis.xlen(settings.event_stream) == 1
        assert await redis.get(progress_key) is not None

        await worker._ensure_group()
        message_id = await redis.xadd(worker._job_stream, {"payload": job.to_json()})
        await redis.xreadgroup(
            groupname=settings.worker_group,
            consumername=settings.consumer_name,
            streams={worker._job_stream: ">"},
            count=1,
        )
        await worker._ack(message_id)
        assert await redis.xlen(worker._job_stream) == 0
    finally:
        await redis.delete(settings.event_stream, worker._job_stream, lock_key, progress_key)
        await redis.aclose()
