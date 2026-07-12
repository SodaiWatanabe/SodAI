from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.model_catalog import ModelId

MODEL_SELECTION_DESCRIPTION = (
    "Model ID. Omit to use Hina for guests or Asuka 1 for authenticated accounts."
)


class CreateConversationRequest(BaseModel):
    input: str = Field(min_length=1, max_length=8000)
    model: ModelId | None = Field(default=None, description=MODEL_SELECTION_DESCRIPTION)


class CreateTurnRequest(BaseModel):
    input: str = Field(min_length=1, max_length=8000)
    model: ModelId | None = Field(default=None, description=MODEL_SELECTION_DESCRIPTION)


class UpdateConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Conversation title cannot be blank")
        return title


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    speaker: Literal["sodai", "partner"]
    content: str
    status: Literal["streaming", "completed", "failed"]
    ordinal: int
    created_at: datetime
    updated_at: datetime


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    input_message_id: UUID
    output_message_id: UUID
    requested_model: ModelId
    resolved_model: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    model: ModelId
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class ConversationResponse(ConversationSummaryResponse):
    messages: list[MessageResponse]
    active_run: RunResponse | None


class ConversationCreationResponse(BaseModel):
    conversation: ConversationResponse
    run: RunResponse


class ConversationListResponse(BaseModel):
    items: list[ConversationSummaryResponse]


class ModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: ModelId
    name: str
    description: str
    is_default: bool


class ModelListResponse(BaseModel):
    items: list[ModelResponse]


class RealtimeTicketResponse(BaseModel):
    ticket: str
    cursor: int
    expires_in: int = 30
