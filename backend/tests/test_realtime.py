import asyncio
from uuid import UUID

import pytest

from app.domain.principals import Principal, PrincipalKind
from app.routers.realtime import next_realtime_message
from app.services.realtime import RealtimeHub, RealtimeTicketService

PRINCIPAL = Principal(
    PrincipalKind.GUEST,
    UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
)
SPACE_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
THREAD_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748c")
REQUEST_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748d")
EXECUTION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748e")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_realtime_ticket_is_single_use() -> None:
    tickets = RealtimeTicketService()
    ticket = tickets.issue(PRINCIPAL)

    assert tickets.consume(ticket) == PRINCIPAL
    assert tickets.consume(ticket) is None


@pytest.mark.anyio
async def test_realtime_idle_connection_receives_heartbeat() -> None:
    queue = asyncio.Queue()

    message = await next_realtime_message(queue, timeout=0)

    assert message == {"type": "ping"}


@pytest.mark.anyio
async def test_realtime_hub_replays_events_after_cursor() -> None:
    hub = RealtimeHub()
    await publish(hub, "response.delta", 2, {"content": "こん"})
    cursor = hub.cursor
    await publish(hub, "response.completed", 3, {"content": "こんにちは"})

    queue, replay = hub.subscribe(PRINCIPAL, cursor)

    assert queue.empty()
    assert [event.type for event in replay] == ["response.completed"]
    assert replay[0].thread_revision == 3
    hub.unsubscribe(PRINCIPAL, queue)


@pytest.mark.anyio
async def test_subscriber_overflow_requires_authoritative_resync() -> None:
    hub = RealtimeHub()
    queue, _ = hub.subscribe(PRINCIPAL, 0)

    for revision in range(1, 258):
        await publish(hub, "response.delta", revision, {"content": str(revision)})

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())

    assert events[0].type == "sync.required"
    assert events[0].thread_revision == 257
    hub.unsubscribe(PRINCIPAL, queue)


@pytest.mark.anyio
async def test_replay_gap_requires_authoritative_resync() -> None:
    hub = RealtimeHub(history_size=2)
    await publish(hub, "response.delta", 1, {"content": "こ"})
    await publish(hub, "response.delta", 2, {"content": "こん"})
    await publish(hub, "response.completed", 3, {"content": "こんにちは"})

    queue, replay = hub.subscribe(PRINCIPAL, 0)

    assert [event.type for event in replay] == ["sync.required"]
    assert replay[0].data == {"reason": "replay_gap"}
    hub.unsubscribe(PRINCIPAL, queue)


async def publish(hub: RealtimeHub, event_type: str, revision: int, data: dict[str, str]) -> None:
    await hub.publish(
        PRINCIPAL,
        event_type=event_type,
        space_id=SPACE_ID,
        thread_id=THREAD_ID,
        thread_revision=revision,
        response_request_id=REQUEST_ID,
        execution_id=EXECUTION_ID,
        data=data,
    )
