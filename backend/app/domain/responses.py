from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.answerers import AnswererId
from app.domain.reasoning import ReasoningEffort

if TYPE_CHECKING:
    from app.domain.threads import Actor, Thread


class ResponseStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResponseEvaluationValue(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class ResponseEvaluation:
    execution_id: UUID
    value: ResponseEvaluationValue
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Execution:
    id: UUID
    response_request_id: UUID
    thread_id: UUID
    result_entry_id: UUID | None
    answerer: AnswererId
    target: str
    status: ResponseStatus
    attempt_no: int
    attempt_id: UUID
    partial_output: str
    resolved_model: str | None
    artifact_id: str | None
    error_code: str | None
    created_at: datetime
    evaluation: ResponseEvaluationValue | None = None


@dataclass(frozen=True, slots=True)
class ResponseRequest:
    id: UUID
    thread_id: UUID
    input_entry_id: UUID
    requested_answerer: AnswererId
    target_actor: Actor
    status: ResponseStatus
    execution: Execution
    created_at: datetime
    reasoning_effort: ReasoningEffort = ReasoningEffort.NONE


@dataclass(frozen=True, slots=True)
class ResponseCreation:
    thread: Thread
    response: ResponseRequest


@dataclass(frozen=True, slots=True)
class ResponseRegeneration:
    thread: Thread
    response: ResponseRequest
    replayed: bool


@dataclass(frozen=True, slots=True)
class ExecutionRetry:
    thread: Thread
    response: ResponseRequest
    execution: Execution
    replayed: bool
