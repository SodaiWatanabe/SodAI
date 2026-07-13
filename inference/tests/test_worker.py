from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    GenerationTurn,
    InferenceSpeaker,
)

from sodai_inference.config import Settings
from sodai_inference.models.hina.engine import GenerationStep
from sodai_inference.worker import InferenceWorker


class StubHina:
    model_name = "hina"
    resolved_model = "hina@artifact"
    manifest = SimpleNamespace(artifact_id="artifact")

    @staticmethod
    def build_prompt(job: GenerationJob) -> list[int]:
        return [1, 2, 3]

    @staticmethod
    def generate(prompt_ids: list[int], job: GenerationJob):
        yield GenerationStep("ab", "ab", 1)
        yield GenerationStep("cd", "abcd", 2)
        yield GenerationStep("", "abcd", 2, FinishReason.STOP)


class RecordingWorker(InferenceWorker):
    def __init__(self, *, fail_at: int | None = None) -> None:
        settings = Settings(
            model_root=Path("."),
            redis_url="redis://localhost",
            redis_password=None,
            device="cpu",
            consumer_name="test",
        )
        super().__init__(settings, None, StubHina())  # type: ignore[arg-type]
        self.events: list[GenerationEvent] = []
        self.fail_at = fail_at

    async def _publish(self, event: GenerationEvent, progress_key: str) -> None:
        self.events.append(event)
        if event.sequence == self.fail_at:
            raise ConnectionError("Redis is unavailable")


class FakeRedis:
    def __init__(self) -> None:
        self.claim_cursors: list[str] = []
        self.eval_args = None

    async def xautoclaim(self, *args, **kwargs):
        self.claim_cursors.append(kwargs["start_id"])
        next_cursor = "70-0" if len(self.claim_cursors) == 1 else "0-0"
        return [next_cursor, [], []]

    async def xreadgroup(self, **kwargs):
        return []

    async def eval(self, *args):
        self.eval_args = args
        return 1


def job() -> GenerationJob:
    return GenerationJob.create(
        execution_id=uuid4(),
        response_request_id=uuid4(),
        attempt_id=uuid4(),
        thread_id=uuid4(),
        answerer_actor_id=uuid4(),
        model="hina",
        artifact_id="artifact",
        turns=(GenerationTurn(InferenceSpeaker.PARTNER, "こんにちは"),),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
    )


def test_attempt_lock_expires_before_a_crashed_job_is_reclaimed() -> None:
    settings = Settings(
        model_root=Path("."),
        redis_url="redis://localhost",
        redis_password=None,
        device="cpu",
        consumer_name="test",
    )

    assert settings.run_lock_seconds * 1_000 < settings.job_claim_idle_ms


@pytest.mark.asyncio
async def test_transport_error_is_not_converted_to_a_later_failed_event() -> None:
    worker = RecordingWorker(fail_at=1)

    with pytest.raises(ConnectionError):
        await worker._generate(job())

    assert [event.type for event in worker.events] == [
        GenerationEventType.STARTED,
        GenerationEventType.DELTA,
    ]
    assert [event.sequence for event in worker.events] == [0, 1]


@pytest.mark.asyncio
async def test_retry_resumes_after_the_atomically_recorded_sequence() -> None:
    worker = RecordingWorker()

    await worker._generate(job(), resume_after_sequence=0)

    assert [event.type for event in worker.events] == [
        GenerationEventType.DELTA,
        GenerationEventType.COMPLETED,
    ]
    assert [event.sequence for event in worker.events] == [1, 2]


@pytest.mark.asyncio
async def test_abandoned_job_scan_continues_from_the_returned_cursor() -> None:
    settings = Settings(
        model_root=Path("."),
        redis_url="redis://localhost",
        redis_password=None,
        device="cpu",
        consumer_name="test",
    )
    redis = FakeRedis()
    worker = InferenceWorker(settings, redis, StubHina())  # type: ignore[arg-type]

    await worker._next_jobs()
    await worker._next_jobs()

    assert redis.claim_cursors == ["0-0", "70-0"]


@pytest.mark.asyncio
async def test_acknowledging_a_job_also_removes_its_payload() -> None:
    settings = Settings(
        model_root=Path("."),
        redis_url="redis://localhost",
        redis_password=None,
        device="cpu",
        consumer_name="test",
    )
    redis = FakeRedis()
    worker = InferenceWorker(settings, redis, StubHina())  # type: ignore[arg-type]

    await worker._ack("30-0")

    assert redis.eval_args[1:] == (1, worker._job_stream, settings.worker_group, "30-0")
