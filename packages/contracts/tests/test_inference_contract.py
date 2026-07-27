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
    GenerationTurn,
    InferenceCorrelation,
    InferenceNamespace,
    InferenceSpeaker,
    MAX_GENERATION_INPUT_BYTES,
    MAX_GENERATION_TURNS,
    log_inference_event,
)


def test_inference_namespace_preserves_production_keys_and_isolates_test_runs() -> None:
    production = InferenceNamespace()
    isolated = InferenceNamespace(f"sodai:e2e:{uuid4().hex}:inference")

    assert production.job_stream == "sodai:inference:jobs:v2"
    assert production.event_stream == "sodai:inference:events:v2"
    assert production.projector_group == "sodai-inference-projector-v2"
    assert production.worker_group == "sodai-inference-workers-v2"
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
        output_tokens=12,
        finish_reason=FinishReason.STOP,
    )

    assert GenerationEvent.from_json(event.to_json()) == event


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
