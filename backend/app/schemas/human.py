from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.reasoning import ReasoningEffort

HumanAnswerText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32000),
]
HumanDraftText = Annotated[str, StringConstraints(max_length=32000)]


class HumanContextEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    author_kind: Literal["human", "model", "agent", "tool", "system"]
    content: str


class HumanAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: UUID
    answerer_name: str
    reasoning_effort: ReasoningEffort
    skip_allowed_until: datetime
    deadline_at: datetime
    draft_content: str
    draft_revision: int
    context: list[HumanContextEntryResponse]


class BrainStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["idle", "waiting", "assigned"]
    rank_name: str
    assignment: HumanAssignmentResponse | None


class HumanAnswerRequest(BaseModel):
    content: HumanAnswerText


class HumanDraftRequest(BaseModel):
    content: HumanDraftText
    revision: int = Field(ge=1, le=9_007_199_254_740_991)


class HumanDraftResponse(BaseModel):
    revision: int


class HumanAnswerSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: UUID
    answerer_name: str
    reasoning_effort: ReasoningEffort
    prompt_preview: str
    answered_at: datetime


class HumanAnswerListResponse(BaseModel):
    items: list[HumanAnswerSummaryResponse]
    next_cursor: str | None


class HumanAnswerDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: UUID
    answerer_name: str
    reasoning_effort: ReasoningEffort
    answered_at: datetime
    context: list[HumanContextEntryResponse]
    answer: str
