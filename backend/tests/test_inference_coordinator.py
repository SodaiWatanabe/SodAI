from uuid import UUID, uuid4

import pytest

from app.domain.execution_events import PendingOutboxEvent
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
