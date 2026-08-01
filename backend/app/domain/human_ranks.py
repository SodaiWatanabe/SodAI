from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from app.domain.answerers import AnswererId

HUMAN_RANK_MIN = 1
HUMAN_RANK_MAX = 3
HUMAN_RANK_POLICY_REVISION = "2026-08-v1"
RATE_BASIS_POINTS = 10_000

HUMAN_RANK_ANSWERERS: Mapping[int, AnswererId] = {
    1: AnswererId.HUMAN_LITE,
    2: AnswererId.HUMAN_STANDARD,
    3: AnswererId.HUMAN_PRO,
}


def _validate_rate(value: int) -> None:
    if not 0 <= value <= RATE_BASIS_POINTS:
        raise ValueError("Human rank rates must be valid basis points")


class HumanRankTrigger(str, Enum):
    ANSWER_COMPLETED = "answer_completed"
    ANSWER_EXPIRED = "answer_expired"
    EVALUATION_SET = "evaluation_set"
    EVALUATION_CLEARED = "evaluation_cleared"
    MANUAL = "manual"


class HumanRankDecisionReason(str, Enum):
    PROMOTION = "promotion"
    QUALITY = "quality"
    RELIABILITY = "reliability"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class HumanRankPromotionRequirement:
    completed_answers: int
    recent_attempts: int
    recent_rated_answers: int
    positive_rate_basis_points: int
    completion_rate_basis_points: int


@dataclass(frozen=True, slots=True)
class HumanRankRetentionRequirement:
    recent_attempts: int
    recent_rated_answers: int
    minimum_positive_rate_basis_points: int
    minimum_completion_rate_basis_points: int


@dataclass(frozen=True, slots=True)
class HumanRankEvidence:
    rank_level: int
    completed_answers: int
    recent_attempts: int
    recent_completed_attempts: int
    recent_rated_answers: int
    recent_positive_answers: int

    @property
    def positive_rate_basis_points(self) -> int | None:
        return _rate_basis_points(
            self.recent_positive_answers,
            self.recent_rated_answers,
        )

    @property
    def completion_rate_basis_points(self) -> int | None:
        return _rate_basis_points(
            self.recent_completed_attempts,
            self.recent_attempts,
        )

    def as_audit_dict(self) -> dict[str, int | None]:
        return {
            "rank_level": self.rank_level,
            "completed_answers": self.completed_answers,
            "recent_attempts": self.recent_attempts,
            "recent_completed_attempts": self.recent_completed_attempts,
            "recent_rated_answers": self.recent_rated_answers,
            "recent_positive_answers": self.recent_positive_answers,
            "positive_rate_basis_points": self.positive_rate_basis_points,
            "completion_rate_basis_points": self.completion_rate_basis_points,
        }


@dataclass(frozen=True, slots=True)
class HumanRankDecision:
    previous_rank_level: int
    rank_level: int
    reason: HumanRankDecisionReason


@dataclass(frozen=True, slots=True)
class HumanRankPolicy:
    revision: str
    promotion_requirements: Mapping[int, HumanRankPromotionRequirement]
    retention_requirements: Mapping[int, HumanRankRetentionRequirement]
    recent_attempt_limit: int = 30
    recent_rating_limit: int = 20

    def __post_init__(self) -> None:
        if not self.revision:
            raise ValueError("Human rank policy revision is required")
        if self.recent_attempt_limit < 1 or self.recent_rating_limit < 1:
            raise ValueError("Human rank evidence windows must be positive")
        for rank_level, requirement in self.promotion_requirements.items():
            if not HUMAN_RANK_MIN <= rank_level < HUMAN_RANK_MAX:
                raise ValueError("Human rank promotion source is outside the catalog")
            if (
                requirement.completed_answers < 1
                or requirement.recent_attempts < 1
                or requirement.recent_rated_answers < 1
                or requirement.recent_attempts > self.recent_attempt_limit
                or requirement.recent_rated_answers > self.recent_rating_limit
            ):
                raise ValueError("Human rank promotion samples are invalid")
            _validate_rate(requirement.positive_rate_basis_points)
            _validate_rate(requirement.completion_rate_basis_points)
        for rank_level, requirement in self.retention_requirements.items():
            if not HUMAN_RANK_MIN < rank_level <= HUMAN_RANK_MAX:
                raise ValueError("Human rank retention level is outside the catalog")
            if (
                requirement.recent_attempts < 1
                or requirement.recent_rated_answers < 1
                or requirement.recent_attempts > self.recent_attempt_limit
                or requirement.recent_rated_answers > self.recent_rating_limit
            ):
                raise ValueError("Human rank retention samples are invalid")
            _validate_rate(requirement.minimum_positive_rate_basis_points)
            _validate_rate(requirement.minimum_completion_rate_basis_points)

    def decide(self, evidence: HumanRankEvidence) -> HumanRankDecision | None:
        retention = self.retention_requirements.get(evidence.rank_level)
        if retention is not None:
            reason = self._demotion_reason(evidence, retention)
            if reason is not None:
                return HumanRankDecision(
                    previous_rank_level=evidence.rank_level,
                    rank_level=evidence.rank_level - 1,
                    reason=reason,
                )

        promotion = self.promotion_requirements.get(evidence.rank_level)
        if promotion is not None and self._meets_promotion(evidence, promotion):
            return HumanRankDecision(
                previous_rank_level=evidence.rank_level,
                rank_level=evidence.rank_level + 1,
                reason=HumanRankDecisionReason.PROMOTION,
            )
        return None

    @staticmethod
    def _meets_promotion(
        evidence: HumanRankEvidence,
        requirement: HumanRankPromotionRequirement,
    ) -> bool:
        positive_rate = evidence.positive_rate_basis_points
        completion_rate = evidence.completion_rate_basis_points
        return (
            evidence.completed_answers >= requirement.completed_answers
            and evidence.recent_attempts >= requirement.recent_attempts
            and evidence.recent_rated_answers >= requirement.recent_rated_answers
            and positive_rate is not None
            and positive_rate >= requirement.positive_rate_basis_points
            and completion_rate is not None
            and completion_rate >= requirement.completion_rate_basis_points
        )

    @staticmethod
    def _demotion_reason(
        evidence: HumanRankEvidence,
        requirement: HumanRankRetentionRequirement,
    ) -> HumanRankDecisionReason | None:
        positive_rate = evidence.positive_rate_basis_points
        if (
            evidence.recent_rated_answers >= requirement.recent_rated_answers
            and positive_rate is not None
            and positive_rate < requirement.minimum_positive_rate_basis_points
        ):
            return HumanRankDecisionReason.QUALITY

        completion_rate = evidence.completion_rate_basis_points
        if (
            evidence.recent_attempts >= requirement.recent_attempts
            and completion_rate is not None
            and completion_rate < requirement.minimum_completion_rate_basis_points
        ):
            return HumanRankDecisionReason.RELIABILITY
        return None


HUMAN_RANK_POLICY = HumanRankPolicy(
    revision=HUMAN_RANK_POLICY_REVISION,
    promotion_requirements={
        1: HumanRankPromotionRequirement(
            completed_answers=20,
            recent_attempts=20,
            recent_rated_answers=10,
            positive_rate_basis_points=8_000,
            completion_rate_basis_points=9_000,
        ),
        2: HumanRankPromotionRequirement(
            completed_answers=50,
            recent_attempts=30,
            recent_rated_answers=20,
            positive_rate_basis_points=9_000,
            completion_rate_basis_points=9_500,
        ),
    },
    retention_requirements={
        2: HumanRankRetentionRequirement(
            recent_attempts=15,
            recent_rated_answers=10,
            minimum_positive_rate_basis_points=6_500,
            minimum_completion_rate_basis_points=7_500,
        ),
        3: HumanRankRetentionRequirement(
            recent_attempts=15,
            recent_rated_answers=10,
            minimum_positive_rate_basis_points=7_500,
            minimum_completion_rate_basis_points=8_000,
        ),
    },
)


def human_answerer_for_rank(rank_level: int) -> AnswererId:
    try:
        return HUMAN_RANK_ANSWERERS[rank_level]
    except KeyError as error:
        raise ValueError(f"unsupported Human rank: {rank_level}") from error


def validate_human_rank(rank_level: int) -> None:
    if not HUMAN_RANK_MIN <= rank_level <= HUMAN_RANK_MAX:
        raise ValueError(f"Human rank must be between {HUMAN_RANK_MIN} and {HUMAN_RANK_MAX}")


def _rate_basis_points(numerator: int, denominator: int) -> int | None:
    if denominator <= 0:
        return None
    return numerator * RATE_BASIS_POINTS // denominator
