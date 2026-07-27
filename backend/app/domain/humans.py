from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.domain.threads import ActorKind

HUMAN_MATCH_LOCK_KEY = 0x534F44414903


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
    context: tuple[HumanContextEntry, ...]


@dataclass(frozen=True, slots=True)
class BrainState:
    status: BrainStatus
    rank_level: int
    rank_name: str
    assignment: HumanAssignment | None = None
