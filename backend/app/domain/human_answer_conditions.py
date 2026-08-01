from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeVar

from app.domain.answerers import AnswererId, get_answerer
from app.domain.reasoning import ReasoningEffort

T = TypeVar("T")

HUMAN_ANSWERER_ORDER = (
    AnswererId.HUMAN_LITE,
    AnswererId.HUMAN_STANDARD,
    AnswererId.HUMAN_PRO,
)
HUMAN_REASONING_EFFORT_ORDER = (
    ReasoningEffort.LOW,
    ReasoningEffort.MEDIUM,
    ReasoningEffort.HIGH,
    ReasoningEffort.XHIGH,
)


@dataclass(frozen=True, slots=True)
class HumanAnswerConditions:
    answerer_ids: tuple[AnswererId, ...]
    reasoning_efforts: tuple[ReasoningEffort, ...]

    def as_model_values(self) -> tuple[list[str], list[str]]:
        return (
            [answerer_id.value for answerer_id in self.answerer_ids],
            [effort.value for effort in self.reasoning_efforts],
        )


DEFAULT_HUMAN_ANSWER_CONDITIONS = HumanAnswerConditions(
    answerer_ids=(AnswererId.HUMAN_LITE,),
    reasoning_efforts=(ReasoningEffort.LOW,),
)


def available_human_answerer_ids(rank_level: int) -> tuple[AnswererId, ...]:
    return tuple(
        answerer_id
        for answerer_id in HUMAN_ANSWERER_ORDER
        if _required_rank(answerer_id) <= rank_level
    )


def validate_human_answer_conditions(
    answerer_ids: Iterable[AnswererId],
    reasoning_efforts: Iterable[ReasoningEffort],
    *,
    rank_level: int,
) -> HumanAnswerConditions:
    ordered_answerers = _ordered_range(
        answerer_ids,
        HUMAN_ANSWERER_ORDER,
        "Human answerers",
    )
    ordered_efforts = _ordered_range(
        reasoning_efforts,
        HUMAN_REASONING_EFFORT_ORDER,
        "Human reasoning efforts",
    )
    if any(_required_rank(answerer_id) > rank_level for answerer_id in ordered_answerers):
        raise ValueError("Selected Human answerer exceeds the current rank")

    effort_set = set(ordered_efforts)
    for answerer_id in ordered_answerers:
        if not _supported_efforts(answerer_id).intersection(effort_set):
            raise ValueError("Every selected Human answerer needs a compatible reasoning effort")
    if any(
        not any(
            effort in _supported_efforts(answerer_id)
            for answerer_id in ordered_answerers
        )
        for effort in ordered_efforts
    ):
        raise ValueError("Every selected reasoning effort needs a compatible Human answerer")
    return HumanAnswerConditions(ordered_answerers, ordered_efforts)


def human_answer_conditions_from_model(
    answerer_ids: Iterable[str],
    reasoning_efforts: Iterable[str],
    *,
    rank_level: int,
) -> HumanAnswerConditions:
    return validate_human_answer_conditions(
        (AnswererId(value) for value in answerer_ids),
        (ReasoningEffort(value) for value in reasoning_efforts),
        rank_level=rank_level,
    )


def clamp_human_answer_conditions(
    conditions: HumanAnswerConditions,
    *,
    rank_level: int,
) -> HumanAnswerConditions:
    available = available_human_answerer_ids(rank_level)
    answerer_ids = tuple(
        answerer_id for answerer_id in conditions.answerer_ids if answerer_id in available
    )
    if not answerer_ids:
        answerer_ids = (available[-1],)

    reasoning_efforts = tuple(
        effort
        for effort in conditions.reasoning_efforts
        if any(
            effort in _supported_efforts(answerer_id)
            for answerer_id in answerer_ids
        )
    )
    if not reasoning_efforts:
        answerer = get_answerer(answerer_ids[-1])
        if answerer is None:
            raise RuntimeError("Human answerer catalog is incomplete")
        reasoning_efforts = (answerer.default_reasoning_effort,)
    return validate_human_answer_conditions(
        answerer_ids,
        reasoning_efforts,
        rank_level=rank_level,
    )


def _required_rank(answerer_id: AnswererId) -> int:
    answerer = get_answerer(answerer_id)
    if answerer is None or answerer.required_human_rank is None:
        raise RuntimeError("Human answerer catalog is incomplete")
    return answerer.required_human_rank


def _supported_efforts(answerer_id: AnswererId) -> frozenset[ReasoningEffort]:
    answerer = get_answerer(answerer_id)
    if answerer is None or answerer.required_human_rank is None:
        raise RuntimeError("Human answerer catalog is incomplete")
    return answerer.supported_reasoning_efforts


def _ordered_range(
    selected: Iterable[T],
    order: tuple[T, ...],
    label: str,
) -> tuple[T, ...]:
    values = tuple(selected)
    if not values or len(set(values)) != len(values):
        raise ValueError(f"{label} must be a non-empty range")
    if any(value not in order for value in values):
        raise ValueError(f"{label} contain an unsupported value")
    selected_set = set(values)
    ordered = tuple(value for value in order if value in selected_set)
    lower = order.index(ordered[0])
    upper = order.index(ordered[-1])
    if ordered != order[lower : upper + 1]:
        raise ValueError(f"{label} must be contiguous")
    return ordered
