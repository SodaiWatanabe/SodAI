from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from app.domain.reasoning import ReasoningEffort
from app.domain.threads import ActorKind

HUMAN_MATCH_LOCK_KEY = 0x534F44414903
HUMAN_SKIP_WINDOW = timedelta(seconds=20)


class BrainStatus(str, Enum):
    IDLE = "idle"
    WAITING = "waiting"
    ASSIGNED = "assigned"


@dataclass(frozen=True, slots=True)
class HumanContextEntry:
    author_kind: ActorKind
    content: str


@dataclass(frozen=True, slots=True)
class HumanAssignment:
    claim_id: UUID
    execution_id: UUID
    answerer_name: str
    reasoning_effort: ReasoningEffort
    skip_allowed_until: datetime
    deadline_at: datetime
    draft_content: str
    draft_revision: int
    context: tuple[HumanContextEntry, ...]


@dataclass(frozen=True, slots=True)
class HumanAnswerSummary:
    execution_id: UUID
    answerer_name: str
    reasoning_effort: ReasoningEffort
    prompt_preview: str
    answered_at: datetime


@dataclass(frozen=True, slots=True)
class HumanAnswerDetail:
    execution_id: UUID
    answerer_name: str
    reasoning_effort: ReasoningEffort
    answered_at: datetime
    context: tuple[HumanContextEntry, ...]
    answer: str


@dataclass(frozen=True, slots=True)
class HumanAnswerPage:
    items: tuple[HumanAnswerSummary, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class BrainState:
    status: BrainStatus
    rank_level: int
    rank_name: str
    assignment: HumanAssignment | None = None
