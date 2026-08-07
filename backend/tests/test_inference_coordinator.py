from uuid import UUID, uuid4

import pytest
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationPhase,
)

from app.domain.execution_events import ExecutionProjection, PendingOutboxEvent
from app.domain.principals import Principal, PrincipalKind
from app.services.inference import coordinator as coordinator_module
from app.services.inference.coordinator import GenerationCoordinator


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self) -> FakeSession:
        return self.session


class FakeRepository:
    def __init__(self, _session: FakeSession, message: PendingOutboxEvent) -> None:
        self.message = message
        self.published: list[UUID] = []

    async def discard_terminal_outbox(self) -> int:
        return 0

    async def pending_cancellation_outbox(self) -> list[PendingOutboxEvent]:
        return [self.message]

    async def pending_outbox(self) -> list[PendingOutboxEvent]:
        return []

    async def mark_outbox_published(self, outbox_id: UUID) -> None:
        self.published.append(outbox_id)


class FakeBroker:
    def __init__(self) -> None:
        self.cancellations: list[tuple[UUID, int]] = []

    async def publish_cancellation(
        self,
        attempt_id: UUID,
        *,
        ttl_seconds: int,
    ) -> None:
        self.cancellations.append((attempt_id, ttl_seconds))


class FakeRealtimeHub:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def publish(self, _principal: Principal, **values: object) -> None:
        self.events.append(values)


@pytest.mark.anyio
async def test_dispatch_publishes_durable_cancellation_with_configured_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt_id = uuid4()
    message = PendingOutboxEvent(
        id=uuid4(),
        execution_id=uuid4(),
        payload=str(attempt_id),
    )
    session = FakeSession()
    repository = FakeRepository(session, message)
    broker = FakeBroker()
    monkeypatch.setattr(
        coordinator_module,
        "SqlAlchemyThreadRepository",
        lambda _session: repository,
    )
    coordinator = GenerationCoordinator(
        FakeSessionFactory(session),  # type: ignore[arg-type]
        broker,  # type: ignore[arg-type]
        cancellation_ttl_seconds=360,
    )

    dispatched = await coordinator._dispatch_pending()

    assert dispatched == 1
    assert broker.cancellations == [(attempt_id, 360)]
    assert repository.published == [message.id]
    assert session.commits == 1


@pytest.mark.anyio
async def test_realtime_publishes_phase_without_thinking_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = Principal(PrincipalKind.USER, uuid4())
    execution_id = uuid4()
    attempt_id = uuid4()
    thread_id = uuid4()
    request_id = uuid4()
    projection = ExecutionProjection(
        principals=(principal,),
        space_id=uuid4(),
        thread_id=thread_id,
        thread_revision=2,
        response_request_id=request_id,
        execution_id=execution_id,
        attempt_id=attempt_id,
        attempt_no=1,
        target_actor_id=uuid4(),
        result_entry_id=None,
        content="公開する回答",
        status="running",
        generation_phase=GenerationPhase.THINKING.value,
    )
    hub = FakeRealtimeHub()
    monkeypatch.setattr(coordinator_module, "realtime_hub", hub)
    coordinator = GenerationCoordinator(
        FakeSessionFactory(FakeSession()),  # type: ignore[arg-type]
        FakeBroker(),  # type: ignore[arg-type]
        cancellation_ttl_seconds=360,
    )

    thinking = GenerationEvent.create(
        GenerationEventType.THINKING_DELTA,
        execution_id=execution_id,
        attempt_id=attempt_id,
        sequence=1,
        thread_id=thread_id,
        delta="非公開の思考",
        output_tokens=2,
        thinking_tokens=2,
    )
    await coordinator._publish_realtime(thinking, projection)
    assert hub.events == []

    phase = GenerationEvent.create(
        GenerationEventType.PHASE_CHANGED,
        execution_id=execution_id,
        attempt_id=attempt_id,
        sequence=2,
        thread_id=thread_id,
        phase=GenerationPhase.ANSWERING,
        output_tokens=3,
        thinking_tokens=2,
        answer_tokens=0,
    )
    await coordinator._publish_realtime(phase, projection)

    assert len(hub.events) == 1
    assert hub.events[0]["event_type"] == "response.phase"
    assert hub.events[0]["data"] == {
        "target_actor_id": str(projection.target_actor_id),
        "result_entry_id": None,
        "phase": "answering",
    }

    completed = GenerationEvent.create(
        GenerationEventType.COMPLETED,
        execution_id=execution_id,
        attempt_id=attempt_id,
        sequence=3,
        thread_id=thread_id,
        content="公開する回答",
        thinking_content="非公開の最終思考",
        output_tokens=5,
        thinking_tokens=2,
        answer_tokens=2,
        finish_reason=FinishReason.STOP,
    )
    await coordinator._publish_realtime(completed, projection)

    assert len(hub.events) == 2
    assert hub.events[1]["event_type"] == "response.completed"
    assert hub.events[1]["data"] == {
        "target_actor_id": str(projection.target_actor_id),
        "result_entry_id": None,
        "content": projection.content,
    }
    assert "非公開の思考" not in str(hub.events)
    assert "非公開の最終思考" not in str(hub.events)
