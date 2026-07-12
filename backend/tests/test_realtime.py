import asyncio
from uuid import UUID

import pytest

from app.domain.conversations import ConversationPrincipal, PrincipalKind
from app.routers.conversations import _next_realtime_message
from app.services.realtime import RealtimeHub, RealtimeTicketService

PRINCIPAL = ConversationPrincipal(
    PrincipalKind.GUEST,
    UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
)
CONVERSATION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
RUN_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748c")


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

    message = await _next_realtime_message(queue, timeout=0)

    assert message == {"type": "ping"}


@pytest.mark.anyio
async def test_realtime_hub_replays_events_after_cursor() -> None:
    hub = RealtimeHub()
    await hub.publish(
        PRINCIPAL,
        "response.delta",
        CONVERSATION_ID,
        RUN_ID,
        {"delta": "こん", "content": "こん"},
    )
    cursor = hub.cursor
    await hub.publish(
        PRINCIPAL,
        "response.completed",
        CONVERSATION_ID,
        RUN_ID,
        {"content": "こんにちは"},
    )

    queue, replay = hub.subscribe(PRINCIPAL, cursor)

    assert queue.empty()
    assert [event.type for event in replay] == ["response.completed"]
    assert replay[0].data["content"] == "こんにちは"
    hub.unsubscribe(PRINCIPAL, queue)


@pytest.mark.anyio
async def test_realtime_hub_bounds_inactive_principal_history() -> None:
    hub = RealtimeHub()
    hub.MAX_PRINCIPAL_HISTORIES = 1
    other = ConversationPrincipal(
        PrincipalKind.GUEST,
        UUID("018f96d4-7c48-7c27-a71f-591e3cb8748f"),
    )
    await hub.publish(PRINCIPAL, "response.delta", CONVERSATION_ID, RUN_ID, {"content": "a"})
    await hub.publish(other, "response.delta", CONVERSATION_ID, RUN_ID, {"content": "b"})

    queue, replay = hub.subscribe(PRINCIPAL, 0)

    assert replay == []
    hub.unsubscribe(PRINCIPAL, queue)
