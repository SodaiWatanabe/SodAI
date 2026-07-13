import asyncio
import secrets
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.principals import Principal


@dataclass(frozen=True, slots=True)
class RealtimeEvent:
    id: UUID
    sequence: int
    type: str
    space_id: UUID
    thread_id: UUID
    thread_revision: int
    response_request_id: UUID | None
    execution_id: UUID | None
    occurred_at: datetime
    data: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "sequence": self.sequence,
            "type": self.type,
            "space_id": str(self.space_id),
            "thread_id": str(self.thread_id),
            "thread_revision": self.thread_revision,
            "response_request_id": (
                str(self.response_request_id) if self.response_request_id else None
            ),
            "execution_id": str(self.execution_id) if self.execution_id else None,
            "occurred_at": self.occurred_at.isoformat(),
            "data": self.data,
        }


class RealtimeHub:
    MAX_PRINCIPAL_HISTORIES = 2048

    def __init__(self, *, history_size: int = 512, subscriber_queue_size: int = 256) -> None:
        if history_size < 1 or subscriber_queue_size < 1:
            raise ValueError("realtime queue sizes must be positive")
        self._history_size = history_size
        self._subscriber_queue_size = subscriber_queue_size
        self._sequence = 0
        self._subscribers: dict[Principal, set[asyncio.Queue[RealtimeEvent]]] = defaultdict(set)
        self._history: OrderedDict[Principal, deque[RealtimeEvent]] = OrderedDict()
        self._evicted_through: dict[Principal, int] = {}

    @property
    def cursor(self) -> int:
        return self._sequence

    async def publish(
        self,
        principal: Principal,
        *,
        event_type: str,
        space_id: UUID,
        thread_id: UUID,
        thread_revision: int,
        response_request_id: UUID | None,
        execution_id: UUID | None,
        data: dict[str, Any],
    ) -> None:
        self._sequence += 1
        event = RealtimeEvent(
            id=uuid4(),
            sequence=self._sequence,
            type=event_type,
            space_id=space_id,
            thread_id=thread_id,
            thread_revision=thread_revision,
            response_request_id=response_request_id,
            execution_id=execution_id,
            occurred_at=datetime.now(timezone.utc),
            data=data,
        )
        history = self._history.setdefault(principal, deque(maxlen=self._history_size))
        if len(history) == self._history_size:
            self._evicted_through[principal] = history[0].sequence
        history.append(event)
        self._history.move_to_end(principal)
        self._evict_inactive_history()
        for queue in tuple(self._subscribers.get(principal, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Once a structural event may have been missed, deltas alone
                # cannot prove convergence. Replace the backlog with an explicit
                # request for an authoritative HTTP snapshot.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(self._sync_required(event, "subscriber_overflow"))

    def subscribe(
        self, principal: Principal, after: int
    ) -> tuple[asyncio.Queue[RealtimeEvent], list[RealtimeEvent]]:
        queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue(maxsize=self._subscriber_queue_size)
        self._subscribers[principal].add(queue)
        history = self._history.setdefault(principal, deque(maxlen=self._history_size))
        self._history.move_to_end(principal)
        evicted_through = self._evicted_through.get(principal)
        if history and evicted_through is not None and after < evicted_through:
            replay = [self._sync_required(history[-1], "replay_gap")]
        else:
            replay = [event for event in history if event.sequence > after]
        return queue, replay

    def unsubscribe(self, principal: Principal, queue: asyncio.Queue[RealtimeEvent]) -> None:
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
            self._evicted_through.pop(inactive, None)

    @staticmethod
    def _sync_required(reference: RealtimeEvent, reason: str) -> RealtimeEvent:
        return RealtimeEvent(
            id=uuid4(),
            sequence=reference.sequence,
            type="sync.required",
            space_id=reference.space_id,
            thread_id=reference.thread_id,
            thread_revision=reference.thread_revision,
            response_request_id=reference.response_request_id,
            execution_id=reference.execution_id,
            occurred_at=datetime.now(timezone.utc),
            data={"reason": reason},
        )


class RealtimeTicketService:
    def __init__(self) -> None:
        self._tickets: dict[str, tuple[Principal, datetime]] = {}

    def issue(self, principal: Principal) -> str:
        self._discard_expired()
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (principal, datetime.now(timezone.utc) + timedelta(seconds=30))
        return ticket

    def consume(self, ticket: str) -> Principal | None:
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
