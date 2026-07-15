from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

HumanAnswerText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32000),
]


class HumanContextEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    author_kind: Literal["human", "model", "agent", "tool", "system"]
    content: str


class HumanAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: UUID
    answerer_name: str
    context: list[HumanContextEntryResponse]


class BrainStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["idle", "waiting", "assigned"]
    rank_name: str
    assignment: HumanAssignmentResponse | None


class HumanAnswerRequest(BaseModel):
    content: HumanAnswerText
