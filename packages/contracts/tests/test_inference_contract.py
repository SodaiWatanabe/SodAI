import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
    GenerationOptions,
    GenerationPhase,
    GenerationTurn,
    InferenceCorrelation,
    InferenceNamespace,
    InferenceSpeaker,
    MAX_GENERATION_INPUT_BYTES,
    MAX_GENERATION_TURNS,
    log_inference_event,
)


def test_generation_options_default_to_128_output_tokens() -> None:
    assert GenerationOptions().max_output_tokens == 128
    assert GenerationOptions.from_dict({}).max_output_tokens == 128


def test_inference_namespace_preserves_production_keys_and_isolates_test_runs() -> None:
    production = InferenceNamespace()
    isolated = InferenceNamespace(f"sodai:e2e:{uuid4().hex}:inference")

    assert production.job_stream == "sodai:inference:jobs:v3"
    assert production.event_stream == "sodai:inference:events:v3"
    assert production.projector_group == "sodai-inference-projector-v3"
    assert production.worker_group == "sodai-inference-workers-v3"
    assert production.worker_readiness("hina", "artifact").endswith(
        ":worker:ready:v3:hina:artifact"
    )
    assert isolated.job_stream != production.job_stream
    assert isolated.attempt_lock(uuid4()).startswith(isolated.prefix)
    assert isolated.attempt_cancellation(uuid4()).endswith(":cancelled")
    assert isolated.worker_readiness("hina", "artifact").startswith(isolated.prefix)


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
        thinking_content="考えました。",
        output_tokens=12,
        thinking_tokens=4,
        answer_tokens=6,
        finish_reason=FinishReason.STOP,
    )

    assert GenerationEvent.from_json(event.to_json()) == event


def test_generation_event_round_trip_preserves_thinking_phase() -> None:
    event = GenerationEvent.create(
        GenerationEventType.THINKING_DELTA,
        execution_id=uuid4(),
        attempt_id=uuid4(),
        sequence=2,
        thread_id=uuid4(),
        delta="考え中",
        output_tokens=3,
        thinking_tokens=3,
    )

    assert GenerationEvent.from_json(event.to_json()) == event

    changed = GenerationEvent.create(
        GenerationEventType.PHASE_CHANGED,
        execution_id=event.execution_id,
        attempt_id=event.attempt_id,
        sequence=3,
        thread_id=event.thread_id,
        phase=GenerationPhase.ANSWERING,
        output_tokens=4,
        thinking_tokens=3,
        answer_tokens=0,
    )
    assert GenerationEvent.from_json(changed.to_json()) == changed


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            {"output_tokens": True, "thinking_tokens": True},
            "output_tokens must be an integer",
        ),
        (
            {"output_tokens": 1, "thinking_tokens": -1},
            "thinking_tokens cannot be negative",
        ),
        (
            {"output_tokens": 1, "thinking_tokens": 2},
            "thinking_tokens cannot exceed output_tokens",
        ),
    ],
)
def test_thinking_event_rejects_invalid_token_counts(values, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        GenerationEvent.create(
            GenerationEventType.THINKING_DELTA,
            execution_id=uuid4(),
            attempt_id=uuid4(),
            sequence=1,
            thread_id=uuid4(),
            delta="考え中",
            **values,
        )


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            {"output_tokens": 1, "answer_tokens": 2},
            "answer_tokens cannot exceed output_tokens",
        ),
        (
            {
                "output_tokens": 2,
                "thinking_tokens": 1,
                "answer_tokens": 2,
            },
            "channel token counts cannot exceed output_tokens",
        ),
    ],
)
def test_generation_event_rejects_channel_counts_beyond_total(
    values, message: str
) -> None:
    event_type = (
        GenerationEventType.DELTA
        if "thinking_tokens" not in values
        else GenerationEventType.PHASE_CHANGED
    )
    event_values = {"delta": "回答"} if event_type is GenerationEventType.DELTA else {
        "phase": GenerationPhase.ANSWERING
    }
    with pytest.raises(ValueError, match=message):
        GenerationEvent.create(
            event_type,
            execution_id=uuid4(),
            attempt_id=uuid4(),
            sequence=1,
            thread_id=uuid4(),
            **event_values,
            **values,
        )


def test_inference_logs_are_correlated_without_prompt_content(caplog) -> None:
    job = GenerationJob.create(
        execution_id=uuid4(),
        response_request_id=uuid4(),
        attempt_id=uuid4(),
        thread_id=uuid4(),
        answerer_actor_id=uuid4(),
        model="hina",
        artifact_id="8f42c9",
        turns=(GenerationTurn(InferenceSpeaker.PARTNER, "秘密のプロンプト"),),
        deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    with caplog.at_level(logging.INFO, logger="test.inference"):
        log_inference_event(
            logging.getLogger("test.inference"),
            logging.INFO,
            "generation_job_claimed",
            InferenceCorrelation.from_job(job),
        )

    payload = json.loads(caplog.records[-1].message)
    assert payload["execution_id"] == str(job.execution_id)
    assert payload["response_request_id"] == str(job.response_request_id)
    assert payload["job_id"] == str(job.id)
    assert "秘密のプロンプト" not in caplog.records[-1].message
