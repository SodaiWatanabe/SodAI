from uuid import uuid4

from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationPhase,
)

from app.domain.execution_events import EventDisposition, classify_generation_event


def event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.STARTED,
        execution_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        thread_id=uuid4(),
        resolved_model="hina@artifact",
        phase=GenerationPhase.ANSWERING,
    )


def completed_event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.COMPLETED,
        execution_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        thread_id=uuid4(),
        content="完了",
        thinking_content="",
        output_tokens=1,
        thinking_tokens=0,
        answer_tokens=1,
        finish_reason=FinishReason.STOP,
    )


def delta_event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.DELTA,
        execution_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        thread_id=uuid4(),
        delta="続き",
        output_tokens=1,
        answer_tokens=1,
    )


def thinking_delta_event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.THINKING_DELTA,
        execution_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        thread_id=uuid4(),
        delta="思考",
        output_tokens=1,
        thinking_tokens=1,
    )


def phase_changed_event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.PHASE_CHANGED,
        execution_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        thread_id=uuid4(),
        phase=GenerationPhase.ANSWERING,
        output_tokens=2,
        thinking_tokens=1,
        answer_tokens=0,
    )


def failed_event(*, attempt_id, sequence: int) -> GenerationEvent:
    return GenerationEvent.create(
        GenerationEventType.FAILED,
        execution_id=uuid4(),
        attempt_id=attempt_id,
        sequence=sequence,
        thread_id=uuid4(),
        error_code="generation_failed",
    )


def classify(
    candidate: GenerationEvent,
    *,
    attempt_id,
    last_sequence: int,
    last_event: GenerationEvent | None = None,
    execution_status: str = "running",
    generation_phase: str | None = "answering",
) -> EventDisposition:
    return classify_generation_event(
        attempt_id=attempt_id,
        last_sequence=last_sequence,
        last_event_id=last_event.id if last_event else None,
        last_event_type=last_event.type.value if last_event else None,
        execution_status=execution_status,
        generation_phase=generation_phase,
        event=candidate,
    )


def test_accepts_only_the_next_event_for_the_active_attempt() -> None:
    attempt_id = uuid4()

    assert (
        classify(
            delta_event(attempt_id=attempt_id, sequence=3),
            attempt_id=attempt_id,
            last_sequence=2,
        )
        is EventDisposition.APPLY
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
        is EventDisposition.REPLAY
    )
    assert (
        classify(
            event(attempt_id=attempt_id, sequence=3),
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=committed,
        )
        is EventDisposition.IGNORE
    )


def test_defers_gaps_and_ignores_events_after_completion() -> None:
    attempt_id = uuid4()

    assert (
        classify(
            event(attempt_id=attempt_id, sequence=5),
            attempt_id=attempt_id,
            last_sequence=3,
        )
        is EventDisposition.DEFER
    )
    assert (
        classify(
            event(attempt_id=attempt_id, sequence=4),
            attempt_id=attempt_id,
            last_sequence=3,
            execution_status="completed",
        )
        is EventDisposition.IGNORE
    )


def test_cancelled_execution_ignores_late_generation_events() -> None:
    attempt_id = uuid4()

    for candidate in (
        delta_event(attempt_id=attempt_id, sequence=4),
        completed_event(attempt_id=attempt_id, sequence=4),
        failed_event(attempt_id=attempt_id, sequence=4),
    ):
        assert (
            classify(
                candidate,
                attempt_id=attempt_id,
                last_sequence=3,
                execution_status="cancelled",
            )
            is EventDisposition.IGNORE
        )


def test_terminal_execution_replays_only_its_exact_terminal_event() -> None:
    attempt_id = uuid4()
    completed = completed_event(attempt_id=attempt_id, sequence=3)

    assert (
        classify(
            completed,
            attempt_id=attempt_id,
            last_sequence=3,
            last_event=completed,
            execution_status="completed",
        )
        is EventDisposition.REPLAY
    )


def test_queued_execution_accepts_only_started_or_failed() -> None:
    attempt_id = uuid4()

    assert (
        classify(
            event(attempt_id=attempt_id, sequence=0),
            attempt_id=attempt_id,
            last_sequence=-1,
            execution_status="queued",
        )
        is EventDisposition.APPLY
    )
    assert (
        classify(
            failed_event(attempt_id=attempt_id, sequence=0),
            attempt_id=attempt_id,
            last_sequence=-1,
            execution_status="queued",
        )
        is EventDisposition.APPLY
    )
    assert (
        classify(
            completed_event(attempt_id=attempt_id, sequence=0),
            attempt_id=attempt_id,
            last_sequence=-1,
            execution_status="queued",
        )
        is EventDisposition.IGNORE
    )
    assert (
        classify(
            delta_event(attempt_id=attempt_id, sequence=0),
            attempt_id=attempt_id,
            last_sequence=-1,
            execution_status="queued",
        )
        is EventDisposition.IGNORE
    )


def test_running_execution_rejects_a_second_started_event() -> None:
    attempt_id = uuid4()

    assert (
        classify(
            event(attempt_id=attempt_id, sequence=1),
            attempt_id=attempt_id,
            last_sequence=0,
            execution_status="running",
        )
        is EventDisposition.IGNORE
    )


def test_thinking_events_cannot_reverse_the_answering_phase() -> None:
    attempt_id = uuid4()
    thinking_delta = thinking_delta_event(attempt_id=attempt_id, sequence=1)
    phase_changed = phase_changed_event(attempt_id=attempt_id, sequence=1)

    for candidate in (thinking_delta, phase_changed):
        assert (
            classify(
                candidate,
                attempt_id=attempt_id,
                last_sequence=0,
                generation_phase="thinking",
            )
            is EventDisposition.APPLY
        )
        assert (
            classify(
                candidate,
                attempt_id=attempt_id,
                last_sequence=0,
                generation_phase="answering",
            )
            is EventDisposition.IGNORE
        )
