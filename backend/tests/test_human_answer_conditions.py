import pytest

from app.domain.answerers import AnswererId
from app.domain.human_answer_conditions import (
    HumanAnswerConditions,
    available_human_answerer_ids,
    clamp_human_answer_conditions,
    validate_human_answer_conditions,
)
from app.domain.reasoning import ReasoningEffort


def test_conditions_are_normalized_to_catalog_order() -> None:
    conditions = validate_human_answer_conditions(
        (AnswererId.HUMAN_PRO, AnswererId.HUMAN_STANDARD),
        (ReasoningEffort.XHIGH, ReasoningEffort.HIGH),
        rank_level=3,
    )

    assert conditions.answerer_ids == (
        AnswererId.HUMAN_STANDARD,
        AnswererId.HUMAN_PRO,
    )
    assert conditions.reasoning_efforts == (
        ReasoningEffort.HIGH,
        ReasoningEffort.XHIGH,
    )


def test_conditions_reject_locked_or_incompatible_options() -> None:
    with pytest.raises(ValueError, match="current rank"):
        validate_human_answer_conditions(
            (AnswererId.HUMAN_PRO,),
            (ReasoningEffort.LOW,),
            rank_level=2,
        )
    with pytest.raises(ValueError, match="compatible reasoning effort"):
        validate_human_answer_conditions(
            (AnswererId.HUMAN_LITE, AnswererId.HUMAN_STANDARD),
            (ReasoningEffort.MEDIUM, ReasoningEffort.HIGH),
            rank_level=2,
        )
    with pytest.raises(ValueError, match="compatible Human answerer"):
        validate_human_answer_conditions(
            (AnswererId.HUMAN_STANDARD,),
            (
                ReasoningEffort.LOW,
                ReasoningEffort.MEDIUM,
                ReasoningEffort.HIGH,
                ReasoningEffort.XHIGH,
            ),
            rank_level=2,
        )


def test_conditions_reject_values_that_cannot_be_represented_as_a_range() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        validate_human_answer_conditions(
            (AnswererId.HUMAN_LITE, AnswererId.HUMAN_PRO),
            (ReasoningEffort.LOW,),
            rank_level=3,
        )
    with pytest.raises(ValueError, match="contiguous"):
        validate_human_answer_conditions(
            (AnswererId.HUMAN_PRO,),
            (ReasoningEffort.LOW, ReasoningEffort.HIGH),
            rank_level=3,
        )


def test_demotion_clamps_conditions_to_the_new_capability() -> None:
    clamped = clamp_human_answer_conditions(
        HumanAnswerConditions(
            (AnswererId.HUMAN_PRO,),
            (ReasoningEffort.XHIGH,),
        ),
        rank_level=2,
    )

    assert clamped == HumanAnswerConditions(
        (AnswererId.HUMAN_STANDARD,),
        (ReasoningEffort.MEDIUM,),
    )


def test_available_answerers_expand_cumulatively_with_rank() -> None:
    assert available_human_answerer_ids(2) == (
        AnswererId.HUMAN_LITE,
        AnswererId.HUMAN_STANDARD,
    )
