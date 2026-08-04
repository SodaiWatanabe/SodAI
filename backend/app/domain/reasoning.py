from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ReasoningEffort(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


@dataclass(frozen=True, slots=True)
class ReasoningEffortDefinition:
    id: ReasoningEffort
    name: str
    execution_time_limit: timedelta | None

    @property
    def execution_time_limit_seconds(self) -> int | None:
        if self.execution_time_limit is None:
            return None
        return int(self.execution_time_limit.total_seconds())


REASONING_EFFORT_CATALOG = (
    ReasoningEffortDefinition(ReasoningEffort.NONE, "なし", None),
    ReasoningEffortDefinition(ReasoningEffort.LOW, "軽い", timedelta(minutes=3)),
    ReasoningEffortDefinition(ReasoningEffort.MEDIUM, "中程度", timedelta(minutes=8)),
    ReasoningEffortDefinition(ReasoningEffort.HIGH, "深い", timedelta(minutes=20)),
    ReasoningEffortDefinition(ReasoningEffort.XHIGH, "非常に深い", timedelta(hours=1)),
)
_REASONING_EFFORTS_BY_ID = {
    definition.id: definition for definition in REASONING_EFFORT_CATALOG
}

if len(_REASONING_EFFORTS_BY_ID) != len(REASONING_EFFORT_CATALOG):
    raise RuntimeError("Reasoning effort catalog contains duplicate identifiers")


def get_reasoning_effort_definition(
    effort: ReasoningEffort,
) -> ReasoningEffortDefinition:
    return _REASONING_EFFORTS_BY_ID[effort]


def reasoning_effort_deadline(
    effort: ReasoningEffort,
    *,
    started_at: datetime,
) -> datetime:
    time_limit = get_reasoning_effort_definition(effort).execution_time_limit
    if time_limit is None:
        raise ValueError("Reasoning effort does not define an execution time limit")
    return started_at + time_limit
