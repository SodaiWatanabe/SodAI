from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    GenerationTurn,
    InferenceSpeaker,
    MAX_GENERATION_INPUT_BYTES,
    MAX_GENERATION_TURNS,
)


def test_generation_job_round_trip_preserves_partner_self_vocabulary() -> None:
    job = GenerationJob.create(
        execution_id=uuid4(),
        response_request_id=uuid4(),
        attempt_id=uuid4(),
        thread_id=uuid4(),
        answerer_actor_id=uuid4(),
        model="hina",
        artifact_id="8f42c9",
        turns=(
            GenerationTurn(InferenceSpeaker.PARTNER, "こんにちは"),
            GenerationTurn(InferenceSpeaker.SELF, "こんにちは。"),
            GenerationTurn(InferenceSpeaker.PARTNER, "あなたは誰ですか？"),
        ),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    restored = GenerationJob.from_json(job.to_json())

    assert restored == job
    assert [turn.speaker.value for turn in restored.turns] == [
        "partner",
        "self",
        "partner",
    ]


def test_generation_job_must_end_with_partner_turn() -> None:
    with pytest.raises(ValueError, match="partner turn"):
        GenerationJob.create(
            execution_id=uuid4(),
            response_request_id=uuid4(),
            attempt_id=uuid4(),
            thread_id=uuid4(),
            answerer_actor_id=uuid4(),
            model="hina",
            artifact_id="8f42c9",
            turns=(GenerationTurn(InferenceSpeaker.SELF, "応答"),),
            deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
        )


def test_generation_job_bounds_history_size() -> None:
    common = {
        "execution_id": uuid4(),
        "response_request_id": uuid4(),
        "attempt_id": uuid4(),
        "thread_id": uuid4(),
        "answerer_actor_id": uuid4(),
        "model": "hina",
        "artifact_id": "8f42c9",
        "deadline": datetime.now(timezone.utc) + timedelta(minutes=5),
    }

    with pytest.raises(ValueError, match="turns"):
        GenerationJob.create(
            **common,
            turns=tuple(
                GenerationTurn(InferenceSpeaker.PARTNER, str(index))
                for index in range(MAX_GENERATION_TURNS + 1)
            ),
        )
    with pytest.raises(ValueError, match="bytes"):
        GenerationJob.create(
            **common,
            turns=(
                GenerationTurn(
                    InferenceSpeaker.PARTNER,
                    "a" * (MAX_GENERATION_INPUT_BYTES + 1),
                ),
            ),
        )


def test_generation_event_round_trip_preserves_completion_metadata() -> None:
    event = GenerationEvent.create(
        GenerationEventType.COMPLETED,
        execution_id=uuid4(),
        attempt_id=uuid4(),
        sequence=13,
        thread_id=uuid4(),
        content="応答",
        output_tokens=12,
        finish_reason=FinishReason.STOP,
    )

    assert GenerationEvent.from_json(event.to_json()) == event
