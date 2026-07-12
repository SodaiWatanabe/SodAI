import asyncio
import secrets
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.conversations import ConversationPrincipal


@dataclass(frozen=True, slots=True)
class RealtimeEvent:
    id: UUID
    sequence: int
    type: str
    conversation_id: UUID
    run_id: UUID | None
    occurred_at: datetime
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "sequence": self.sequence,
            "type": self.type,
            "conversation_id": str(self.conversation_id),
            "run_id": str(self.run_id) if self.run_id else None,
            "occurred_at": self.occurred_at.isoformat(),
            "data": self.data,
        }


class RealtimeHub:
    MAX_PRINCIPAL_HISTORIES = 2048

    def __init__(self) -> None:
        self._sequence = 0
        self._subscribers: dict[ConversationPrincipal, set[asyncio.Queue[RealtimeEvent]]] = (
            defaultdict(set)
        )
        self._history: OrderedDict[ConversationPrincipal, deque[RealtimeEvent]] = OrderedDict()

    @property
    def cursor(self) -> int:
        return self._sequence

    async def publish(
        self,
        principal: ConversationPrincipal,
        event_type: str,
        conversation_id: UUID,
        run_id: UUID | None,
        data: dict[str, Any],
    ) -> None:
        self._sequence += 1
        event = RealtimeEvent(
            id=uuid4(),
            sequence=self._sequence,
            type=event_type,
            conversation_id=conversation_id,
            run_id=run_id,
            occurred_at=datetime.now(timezone.utc),
            data=data,
        )
        history = self._history.setdefault(principal, deque(maxlen=512))
        history.append(event)
        self._history.move_to_end(principal)
        self._evict_inactive_history()
        for queue in tuple(self._subscribers.get(principal, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Deltas contain cumulative content, so keeping the newest event
                # lets a slow connection converge without becoming silently stale.
                queue.get_nowait()
                queue.put_nowait(event)

    def subscribe(
        self, principal: ConversationPrincipal, after: int
    ) -> tuple[asyncio.Queue[RealtimeEvent], list[RealtimeEvent]]:
        queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue(maxsize=256)
        self._subscribers[principal].add(queue)
        history = self._history.setdefault(principal, deque(maxlen=512))
        self._history.move_to_end(principal)
        replay = [event for event in history if event.sequence > after]
        return queue, replay

    def unsubscribe(
        self, principal: ConversationPrincipal, queue: asyncio.Queue[RealtimeEvent]
    ) -> None:
        self._subscribers[principal].discard(queue)
        if not self._subscribers[principal]:
            self._subscribers.pop(principal, None)

    def _evict_inactive_history(self) -> None:
        while len(self._history) > self.MAX_PRINCIPAL_HISTORIES:
            inactive = next(
                (principal for principal in self._history if principal not in self._subscribers),
                None,
            )
            if inactive is None:
                return
            self._history.pop(inactive, None)


class RealtimeTicketService:
    def __init__(self) -> None:
        self._tickets: dict[str, tuple[ConversationPrincipal, datetime]] = {}

    def issue(self, principal: ConversationPrincipal) -> str:
        self._discard_expired()
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (principal, datetime.now(timezone.utc) + timedelta(seconds=30))
        return ticket

    def consume(self, ticket: str) -> ConversationPrincipal | None:
        self._discard_expired()
        value = self._tickets.pop(ticket, None)
        return value[0] if value else None

    def _discard_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [ticket for ticket, (_, expires_at) in self._tickets.items() if expires_at <= now]
        for ticket in expired:
            self._tickets.pop(ticket, None)


realtime_hub = RealtimeHub()
realtime_tickets = RealtimeTicketService()
