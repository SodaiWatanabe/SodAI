from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from sodai_contracts.inference import GenerationEvent, GenerationEventType

from app.domain.conversations import ConversationPrincipal


@dataclass(frozen=True, slots=True)
class PendingInferenceOutbox:
    id: UUID
    payload: str


@dataclass(frozen=True, slots=True)
class InferenceProjection:
    principal: ConversationPrincipal
    conversation_id: UUID
    run_id: UUID
    output_message_id: UUID
    content: str


class InferenceEventDisposition(str, Enum):
    APPLY = "apply"
    REPLAY = "replay"
    IGNORE = "ignore"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class InferenceProjectionResult:
    disposition: InferenceEventDisposition
    projection: InferenceProjection | None = None


def classify_inference_event(
    *,
    attempt_id: UUID,
    last_sequence: int,
    last_event_id: UUID | None,
    last_event_type: str | None,
    run_status: str,
    event: GenerationEvent,
) -> InferenceEventDisposition:
    if event.attempt_id != attempt_id or event.sequence < last_sequence:
        return InferenceEventDisposition.IGNORE
    if event.sequence == last_sequence:
        if event.id != last_event_id or event.type.value != last_event_type:
            return InferenceEventDisposition.IGNORE
        if run_status in {"completed", "failed"} and event.type not in {
            GenerationEventType.COMPLETED,
            GenerationEventType.FAILED,
        }:
            return InferenceEventDisposition.IGNORE
        return InferenceEventDisposition.REPLAY
    if run_status in {"completed", "failed"}:
        return InferenceEventDisposition.IGNORE
    if event.sequence == last_sequence + 1:
        return InferenceEventDisposition.APPLY
    return InferenceEventDisposition.DEFER
