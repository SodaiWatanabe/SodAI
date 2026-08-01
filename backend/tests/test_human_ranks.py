import pytest

from app.domain.human_ranks import (
    HUMAN_RANK_POLICY,
    HumanRankDecisionReason,
    HumanRankEvidence,
    HumanRankPolicy,
    HumanRankPromotionRequirement,
    validate_human_rank,
)


def evidence(
    rank_level: int,
    *,
    completed: int,
    attempts: int,
    recent_completed: int,
    rated: int,
    positive: int,
) -> HumanRankEvidence:
    return HumanRankEvidence(
        rank_level=rank_level,
        completed_answers=completed,
        recent_attempts=attempts,
        recent_completed_attempts=recent_completed,
        recent_rated_answers=rated,
        recent_positive_answers=positive,
    )


def test_lite_promotes_only_after_every_requirement_is_met() -> None:
    qualified = evidence(
        1,
        completed=20,
        attempts=20,
        recent_completed=18,
        rated=10,
        positive=8,
    )
    decision = HUMAN_RANK_POLICY.decide(qualified)
    assert decision is not None
    assert decision.previous_rank_level == 1
    assert decision.rank_level == 2
    assert decision.reason is HumanRankDecisionReason.PROMOTION

    assert (
        HUMAN_RANK_POLICY.decide(
            evidence(
                1,
                completed=19,
                attempts=20,
                recent_completed=18,
                rated=10,
                positive=8,
            )
        )
        is None
    )
    assert (
        HUMAN_RANK_POLICY.decide(
            evidence(
                1,
                completed=20,
                attempts=20,
                recent_completed=18,
                rated=10,
                positive=7,
            )
        )
        is None
    )


def test_standard_uses_hysteresis_between_promotion_and_demotion() -> None:
    maintained = evidence(
        2,
        completed=50,
        attempts=30,
        recent_completed=28,
        rated=20,
        positive=16,
    )
    assert HUMAN_RANK_POLICY.decide(maintained) is None

    promoted = evidence(
        2,
        completed=50,
        attempts=30,
        recent_completed=29,
        rated=20,
        positive=18,
    )
    decision = HUMAN_RANK_POLICY.decide(promoted)
    assert decision is not None
    assert decision.rank_level == 3
    assert decision.reason is HumanRankDecisionReason.PROMOTION


def test_demotion_requires_enough_recent_evidence() -> None:
    too_few_ratings = evidence(
        3,
        completed=9,
        attempts=9,
        recent_completed=9,
        rated=9,
        positive=0,
    )
    assert HUMAN_RANK_POLICY.decide(too_few_ratings) is None

    quality_failure = evidence(
        3,
        completed=10,
        attempts=10,
        recent_completed=10,
        rated=10,
        positive=7,
    )
    decision = HUMAN_RANK_POLICY.decide(quality_failure)
    assert decision is not None
    assert decision.rank_level == 2
    assert decision.reason is HumanRankDecisionReason.QUALITY

    reliability_failure = evidence(
        2,
        completed=11,
        attempts=15,
        recent_completed=11,
        rated=0,
        positive=0,
    )
    decision = HUMAN_RANK_POLICY.decide(reliability_failure)
    assert decision is not None
    assert decision.rank_level == 1
    assert decision.reason is HumanRankDecisionReason.RELIABILITY


@pytest.mark.parametrize("rank_level", [0, 4])
def test_rank_validation_rejects_levels_outside_the_catalog(rank_level: int) -> None:
    with pytest.raises(ValueError):
        validate_human_rank(rank_level)


def test_policy_rejects_requirements_larger_than_the_evidence_window() -> None:
    with pytest.raises(ValueError, match="samples"):
        HumanRankPolicy(
            revision="invalid",
            promotion_requirements={
                1: HumanRankPromotionRequirement(
                    completed_answers=1,
                    recent_attempts=31,
                    recent_rated_answers=1,
                    positive_rate_basis_points=8_000,
                    completion_rate_basis_points=9_000,
                )
            },
            retention_requirements={},
        )
