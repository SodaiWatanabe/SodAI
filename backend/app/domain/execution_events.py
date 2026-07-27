from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from sodai_contracts.inference import GenerationEvent, GenerationEventType

from app.domain.principals import Principal


class EventDisposition(str, Enum):
    APPLY = "apply"
    REPLAY = "replay"
    IGNORE = "ignore"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class PendingOutboxEvent:
    id: UUID
    execution_id: UUID
    payload: str


TERMINAL_EXECUTION_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class ExecutionProjection:
    principals: tuple[Principal, ...]
    space_id: UUID
    thread_id: UUID
    thread_revision: int
    response_request_id: UUID
    execution_id: UUID
    attempt_id: UUID
    attempt_no: int
    target_actor_id: UUID
    result_entry_id: UUID | None
    content: str
    status: str
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    disposition: EventDisposition
    projection: ExecutionProjection | None = None


def classify_generation_event(
    *,
    attempt_id: UUID,
    last_sequence: int,
    last_event_id: UUID | None,
    last_event_type: str | None,
    execution_status: str,
    event: GenerationEvent,
) -> EventDisposition:
    if event.attempt_id != attempt_id or event.sequence < last_sequence:
        return EventDisposition.IGNORE
    if event.sequence == last_sequence:
        if event.id != last_event_id or event.type.value != last_event_type:
            return EventDisposition.IGNORE
        if execution_status in TERMINAL_EXECUTION_STATUSES and event.type not in {
            GenerationEventType.COMPLETED,
            GenerationEventType.FAILED,
        }:
            return EventDisposition.IGNORE
        return EventDisposition.REPLAY
    if execution_status in TERMINAL_EXECUTION_STATUSES:
        return EventDisposition.IGNORE
    if event.sequence == last_sequence + 1:
        allowed_events = {
            "queued": {GenerationEventType.STARTED, GenerationEventType.FAILED},
            "running": {
                GenerationEventType.DELTA,
                GenerationEventType.HEARTBEAT,
                GenerationEventType.COMPLETED,
                GenerationEventType.FAILED,
            },
        }
        if event.type in allowed_events.get(execution_status, set()):
            return EventDisposition.APPLY
        return EventDisposition.IGNORE
    return EventDisposition.DEFER
