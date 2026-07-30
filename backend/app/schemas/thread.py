from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.answerers import AnswererId, AnswererKind, AnswererPricingKind
from app.domain.reasoning import ReasoningEffort

ANSWERER_SELECTION_DESCRIPTION = (
    "Answerer ID. Omit to use Hina for guests or Asuka 1 for authenticated accounts."
)
InputText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=8000),
]
ThreadTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
ThreadSearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class CreateThreadRequest(BaseModel):
    input: InputText
    answerer: AnswererId | None = Field(default=None, description=ANSWERER_SELECTION_DESCRIPTION)
    reasoning_effort: ReasoningEffort | None = None


class CreateResponseRequest(BaseModel):
    thread_id: UUID
    input: InputText
    answerer: AnswererId | None = Field(default=None, description=ANSWERER_SELECTION_DESCRIPTION)
    reasoning_effort: ReasoningEffort | None = None


class UpdateThreadRequest(BaseModel):
    title: ThreadTitle


class ThreadSearchRequest(BaseModel):
    query: ThreadSearchQuery
    limit: int = Field(default=20, ge=1, le=50)


class ActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: Literal["human", "model", "agent", "tool", "system"]
    name: str


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    author: ActorResponse
    kind: Literal["message"]
    content: str
    ordinal: int
    created_at: datetime
    answerer: AnswererId | None = None
    response_status: Literal["completed", "cancelled"] | None = None


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_request_id: UUID
    thread_id: UUID
    result_entry_id: UUID | None
    answerer: AnswererId
    target: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    attempt_no: int
    attempt_id: UUID
    partial_output: str
    resolved_model: str | None
    error_code: str | None
    created_at: datetime


class ResponseRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    input_entry_id: UUID
    requested_answerer: AnswererId
    reasoning_effort: ReasoningEffort
    target_actor: ActorResponse
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    execution: ExecutionResponse
    created_at: datetime


class SpaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: Literal["personal", "shared"]
    name: str | None
    created_at: datetime


class SpaceListResponse(BaseModel):
    items: list[SpaceResponse]


class ThreadSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    space_id: UUID
    title: str
    answerer: AnswererId
    revision: int
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class ThreadResponse(ThreadSummaryResponse):
    entries: list[EntryResponse]
    latest_response: ResponseRequestResponse | None


class ResponseCreationResponse(BaseModel):
    thread: ThreadResponse
    response: ResponseRequestResponse


class ThreadListResponse(BaseModel):
    items: list[ThreadSummaryResponse]


class ThreadSearchHitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread: ThreadSummaryResponse
    source: Literal["title", "entry"]
    entry_id: UUID | None
    snippet: str


class ThreadSearchResponse(BaseModel):
    items: list[ThreadSearchHitResponse]
    has_more: bool


class AnswererPricingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: AnswererPricingKind
    asset_code: str
    scale: int
    tariff_revision: str
    fixed_charge: int
    input_token_rate: int
    output_token_rate: int
    maximum_charge: int
    unmetered_charge: int


class AvailableReasoningEffortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: ReasoningEffort
    name: str
    execution_time_limit_seconds: int | None


class AnswererResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: AnswererId
    name: str
    description: str
    kind: AnswererKind
    is_default: bool
    is_legacy: bool
    pricing: AnswererPricingResponse
    reasoning_efforts: list[AvailableReasoningEffortResponse]
    default_reasoning_effort: ReasoningEffort


class AnswererListResponse(BaseModel):
    items: list[AnswererResponse]


class RealtimeTicketResponse(BaseModel):
    ticket: str
    cursor: int
    expires_in: int = 30
