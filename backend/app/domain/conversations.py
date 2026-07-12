from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class PrincipalKind(str, Enum):
    USER = "user"
    GUEST = "guest"


class Speaker(str, Enum):
    """A speaker named from SodAI's point of view."""

    SODAI = "sodai"
    PARTNER = "partner"


class MessageStatus(str, Enum):
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ConversationPrincipal:
    kind: PrincipalKind
    id: UUID


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    id: UUID
    title: str
    model: str
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


@dataclass(frozen=True, slots=True)
class Message:
    id: UUID
    conversation_id: UUID
    speaker: Speaker
    content: str
    status: MessageStatus
    ordinal: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class InferenceRun:
    id: UUID
    conversation_id: UUID
    input_message_id: UUID
    output_message_id: UUID
    requested_model: str
    resolved_model: str
    status: RunStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Conversation:
    id: UUID
    title: str
    model: str
    messages: tuple[Message, ...]
    active_run: InferenceRun | None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


@dataclass(frozen=True, slots=True)
class ConversationCreation:
    conversation: Conversation
    run: InferenceRun
