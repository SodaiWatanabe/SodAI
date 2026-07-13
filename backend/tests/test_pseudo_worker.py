from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sodai_contracts.inference import (
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    GenerationTurn,
    InferenceSpeaker,
)

from app.services.inference.asuka import ASUKA_PSEUDO_ARTIFACT_ID, AsukaPseudoGenerator
from app.services.inference.pseudo_worker import PUBLISH_EVENT_SCRIPT, PseudoGenerationWorker


class RecordingRedis:
    def __init__(self) -> None:
        self.payloads: list[str] = []
        self.progress: list[str] = []

    async def eval(self, script, key_count, *values):
        assert script == PUBLISH_EVENT_SCRIPT
        assert key_count == 3
        assert values[0] == "events"
        self.payloads.append(values[3])
        self.progress.append(values[4])
        return "1-0"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_asuka_emits_the_shared_generation_event_contract() -> None:
    redis = RecordingRedis()
    generator = AsukaPseudoGenerator()
    generator.chunk_interval_seconds = 0
    worker = PseudoGenerationWorker(
        redis,  # type: ignore[arg-type]
        generator,
        job_stream="jobs",
        event_stream="events",
        worker_group="workers",
        consumer_name="test",
    )
    job = GenerationJob.create(
        execution_id=uuid4(),
        response_request_id=uuid4(),
        attempt_id=uuid4(),
        thread_id=uuid4(),
        answerer_actor_id=uuid4(),
        model="asuka-1",
        artifact_id=ASUKA_PSEUDO_ARTIFACT_ID,
        turns=(GenerationTurn(InferenceSpeaker.PARTNER, "こんにちは"),),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=1),
    )

    await worker._generate(job)

    events = [GenerationEvent.from_json(payload) for payload in redis.payloads]
    assert events[0].type is GenerationEventType.STARTED
    assert events[-1].type is GenerationEventType.COMPLETED
    assert all(event.execution_id == job.execution_id for event in events)
    assert events[-1].content and len(events[-1].content) > 80
    assert '"terminal":true' in redis.progress[-1]
