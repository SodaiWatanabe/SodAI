from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.answerers import AnswererId

if TYPE_CHECKING:
    from app.domain.responses import ResponseRequest


class ActorKind(str, Enum):
    HUMAN = "human"
    MODEL = "model"
    AGENT = "agent"
    TOOL = "tool"
    SYSTEM = "system"


class EntryKind(str, Enum):
    MESSAGE = "message"


class ThreadSearchSource(str, Enum):
    TITLE = "title"
    ENTRY = "entry"


@dataclass(frozen=True, slots=True)
class Actor:
    id: UUID
    kind: ActorKind
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class SpaceSummary:
    id: UUID
    kind: str
    name: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ThreadSummary:
    id: UUID
    space_id: UUID
    title: str
    answerer: AnswererId
    revision: int
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


@dataclass(frozen=True, slots=True)
class ThreadSearchHit:
    thread: ThreadSummary
    source: ThreadSearchSource
    entry_id: UUID | None
    snippet: str


@dataclass(frozen=True, slots=True)
class ThreadSearchPage:
    items: tuple[ThreadSearchHit, ...]
    has_more: bool


@dataclass(frozen=True, slots=True)
class Entry:
    id: UUID
    thread_id: UUID
    author: Actor
    kind: EntryKind
    content: str
    ordinal: int
    created_at: datetime
    answerer: AnswererId | None = None


@dataclass(frozen=True, slots=True)
class Thread:
    id: UUID
    space_id: UUID
    title: str
    answerer: AnswererId
    revision: int
    entries: tuple[Entry, ...]
    latest_response: ResponseRequest | None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
