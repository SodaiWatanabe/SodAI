from uuid import uuid4

from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
)

from app.domain.inference import InferenceEventDisposition, classify_inference_event


def event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.STARTED,
        run_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        conversation_id=uuid4(),
        resolved_model="hina@artifact",
    )


def completed_event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.COMPLETED,
        run_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        conversation_id=uuid4(),
        content="完了",
        output_tokens=1,
        finish_reason=FinishReason.STOP,
    )


def classify(
    candidate: GenerationEvent,
    *,
    attempt_id,
    last_sequence: int,
    last_event: GenerationEvent | None = None,
    run_status: str = "running",
) -> InferenceEventDisposition:
    return classify_inference_event(
        attempt_id=attempt_id,
        last_sequence=last_sequence,
        last_event_id=last_event.id if last_event else None,
        last_event_type=last_event.type.value if last_event else None,
        run_status=run_status,
        event=candidate,
    )


def test_accepts_only_the_next_event_for_the_active_attempt() -> None:
    attempt_id = uuid4()

    assert (
        classify(
            event(attempt_id=attempt_id, sequence=3),
            attempt_id=attempt_id,
            last_sequence=2,
        )
        is InferenceEventDisposition.APPLY
    )


def test_replays_only_the_exact_latest_committed_event() -> None:
    attempt_id = uuid4()
    committed = event(attempt_id=attempt_id, sequence=3)

    assert (
        classify(
            committed,
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=committed,
        )
        is InferenceEventDisposition.REPLAY
    )
    assert (
        classify(
            event(attempt_id=attempt_id, sequence=3),
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=committed,
        )
        is InferenceEventDisposition.IGNORE
    )


def test_rejects_old_events_and_defers_sequence_gaps() -> None:
    attempt_id = uuid4()
    committed = event(attempt_id=attempt_id, sequence=3)

    assert (
        classify(
            event(attempt_id=attempt_id, sequence=2),
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=committed,
        )
        is InferenceEventDisposition.IGNORE
    )
    assert (
        classify(
            event(attempt_id=attempt_id, sequence=5),
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=committed,
        )
        is InferenceEventDisposition.DEFER
    )


def test_rejects_old_attempts_and_events_after_terminal_state() -> None:
    attempt_id = uuid4()

    assert (
        classify(
            event(attempt_id=uuid4(), sequence=0),
            attempt_id=attempt_id,
            last_sequence=-1,
            run_status="queued",
        )
        is InferenceEventDisposition.IGNORE
    )
    assert (
        classify(
            event(attempt_id=attempt_id, sequence=4),
            attempt_id=attempt_id,
            last_sequence=3,
            run_status="completed",
        )
        is InferenceEventDisposition.IGNORE
    )


def test_terminal_run_replays_only_its_exact_terminal_event() -> None:
    attempt_id = uuid4()
    completed = completed_event(attempt_id=attempt_id, sequence=3)
    started = event(attempt_id=attempt_id, sequence=3)

    assert (
        classify(
            completed,
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=completed,
            run_status="completed",
        )
        is InferenceEventDisposition.REPLAY
    )
    assert (
        classify(
            started,
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=started,
            run_status="failed",
        )
        is InferenceEventDisposition.IGNORE
    )
