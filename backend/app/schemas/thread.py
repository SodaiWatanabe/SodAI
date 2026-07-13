from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.answerers import AnswererId

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


class CreateThreadRequest(BaseModel):
    input: InputText
    answerer: AnswererId | None = Field(default=None, description=ANSWERER_SELECTION_DESCRIPTION)


class CreateResponseRequest(BaseModel):
    thread_id: UUID
    input: InputText
    answerer: AnswererId | None = Field(default=None, description=ANSWERER_SELECTION_DESCRIPTION)


class UpdateThreadRequest(BaseModel):
    title: ThreadTitle


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


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_request_id: UUID
    thread_id: UUID
    result_entry_id: UUID | None
    answerer: AnswererId
    target: str
    status: Literal["queued", "running", "completed", "failed"]
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
    target_actor: ActorResponse
    status: Literal["queued", "running", "completed", "failed"]
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


class AnswererResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: AnswererId
    name: str
    description: str
    is_default: bool


class AnswererListResponse(BaseModel):
    items: list[AnswererResponse]


class RealtimeTicketResponse(BaseModel):
    ticket: str
    cursor: int
    expires_in: int = 30
