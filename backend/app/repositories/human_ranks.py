from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.human_answer_conditions import (
    DEFAULT_HUMAN_ANSWER_CONDITIONS,
    clamp_human_answer_conditions,
    human_answer_conditions_from_model,
)
from app.domain.human_ranks import (
    HUMAN_RANK_POLICY,
    HumanRankDecisionReason,
    HumanRankEvidence,
    HumanRankPolicy,
    HumanRankTrigger,
    human_answerer_for_rank,
    validate_human_rank,
)
from app.domain.humans import HUMAN_MATCH_LOCK_KEY
from app.models.humans import (
    HumanClaimModel,
    HumanProfileModel,
    HumanRankEventModel,
    HumanWaitEntryModel,
)
from app.models.platform import (
    ExecutionModel,
    ResponseEvaluationModel,
    ResponseRequestModel,
)


class SqlAlchemyHumanRankRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        policy: HumanRankPolicy = HUMAN_RANK_POLICY,
    ) -> None:
        self._session = session
        self._policy = policy

    async def recalculate(
        self,
        user_id: UUID,
        trigger: HumanRankTrigger,
        *,
        trigger_execution_id: UUID | None,
    ) -> None:
        await self._lock_matching()
        profile = await self._locked_profile(user_id)
        if profile is None:
            return

        evidence = await self._evidence(profile)
        decision = self._policy.decide(evidence)
        if decision is None:
            return

        now = datetime.now(timezone.utc)
        conditions = clamp_human_answer_conditions(
            human_answer_conditions_from_model(
                profile.accepted_answerer_ids,
                profile.accepted_reasoning_efforts,
                rank_level=profile.rank_level,
            ),
            rank_level=decision.rank_level,
        )
        answerer_ids, reasoning_efforts = conditions.as_model_values()
        profile.rank_level = decision.rank_level
        profile.rank_changed_at = now
        profile.accepted_answerer_ids = answerer_ids
        profile.accepted_reasoning_efforts = reasoning_efforts
        profile.updated_at = now
        await self._update_waiting_rank(user_id, decision.rank_level)
        self._session.add(
            HumanRankEventModel(
                id=uuid4(),
                performer_user_id=user_id,
                previous_rank_level=decision.previous_rank_level,
                rank_level=decision.rank_level,
                policy_revision=self._policy.revision,
                trigger_kind=trigger.value,
                trigger_execution_id=trigger_execution_id,
                reason=decision.reason.value,
                evidence=evidence.as_audit_dict(),
            )
        )
        await self._session.flush()

    async def recalculate_for_execution(
        self,
        execution_id: UUID,
        trigger: HumanRankTrigger,
    ) -> None:
        performer_user_id = await self._session.scalar(
            select(HumanClaimModel.performer_user_id).where(
                HumanClaimModel.execution_id == execution_id,
                HumanClaimModel.status == "answered",
            )
        )
        if performer_user_id is None:
            return
        await self.recalculate(
            performer_user_id,
            trigger,
            trigger_execution_id=execution_id,
        )

    async def set_manual_rank(self, user_id: UUID, rank_level: int) -> None:
        validate_human_rank(rank_level)
        await self._lock_matching()
        now = datetime.now(timezone.utc)
        profile = await self._locked_profile(user_id)
        if profile is None:
            previous_rank_level = 1
            answerer_ids, reasoning_efforts = (
                DEFAULT_HUMAN_ANSWER_CONDITIONS.as_model_values()
            )
            profile = HumanProfileModel(
                user_id=user_id,
                rank_level=rank_level,
                rank_changed_at=now,
                accepted_answerer_ids=answerer_ids,
                accepted_reasoning_efforts=reasoning_efforts,
                created_at=now,
                updated_at=now,
            )
            self._session.add(profile)
            evidence = self._empty_evidence()
        else:
            previous_rank_level = profile.rank_level
            evidence = await self._evidence(profile)

        if previous_rank_level != rank_level:
            conditions = clamp_human_answer_conditions(
                human_answer_conditions_from_model(
                    profile.accepted_answerer_ids,
                    profile.accepted_reasoning_efforts,
                    rank_level=profile.rank_level,
                ),
                rank_level=rank_level,
            )
            answerer_ids, reasoning_efforts = conditions.as_model_values()
            profile.rank_level = rank_level
            profile.rank_changed_at = now
            profile.accepted_answerer_ids = answerer_ids
            profile.accepted_reasoning_efforts = reasoning_efforts
            profile.updated_at = now
            self._session.add(
                HumanRankEventModel(
                    id=uuid4(),
                    performer_user_id=user_id,
                    previous_rank_level=previous_rank_level,
                    rank_level=rank_level,
                    policy_revision=self._policy.revision,
                    trigger_kind=HumanRankTrigger.MANUAL.value,
                    trigger_execution_id=None,
                    reason=HumanRankDecisionReason.MANUAL.value,
                    evidence=evidence.as_audit_dict(),
                )
            )
        await self._update_waiting_rank(user_id, rank_level)
        await self._session.flush()

    async def _evidence(self, profile: HumanProfileModel) -> HumanRankEvidence:
        answerer = human_answerer_for_rank(profile.rank_level)
        common_filters = (
            HumanClaimModel.performer_user_id == profile.user_id,
            HumanClaimModel.claimed_at >= profile.rank_changed_at,
            ResponseRequestModel.requested_answerer == answerer.value,
        )
        completed_answers = await self._session.scalar(
            select(func.count())
            .select_from(HumanClaimModel)
            .join(
                ExecutionModel,
                ExecutionModel.id == HumanClaimModel.execution_id,
            )
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .where(*common_filters, HumanClaimModel.status == "answered")
        )
        recent_statuses = (
            await self._session.scalars(
                select(HumanClaimModel.status)
                .join(
                    ExecutionModel,
                    ExecutionModel.id == HumanClaimModel.execution_id,
                )
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .where(
                    *common_filters,
                    HumanClaimModel.status.in_(("answered", "expired")),
                )
                .order_by(
                    HumanClaimModel.finished_at.desc(),
                    HumanClaimModel.id.desc(),
                )
                .limit(self._policy.recent_attempt_limit)
            )
        ).all()
        recent_ratings = (
            await self._session.scalars(
                select(ResponseEvaluationModel.value)
                .select_from(HumanClaimModel)
                .join(
                    ExecutionModel,
                    ExecutionModel.id == HumanClaimModel.execution_id,
                )
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .join(
                    ResponseEvaluationModel,
                    ResponseEvaluationModel.execution_id == ExecutionModel.id,
                )
                .where(*common_filters, HumanClaimModel.status == "answered")
                .order_by(
                    HumanClaimModel.finished_at.desc(),
                    HumanClaimModel.id.desc(),
                )
                .limit(self._policy.recent_rating_limit)
            )
        ).all()
        return HumanRankEvidence(
            rank_level=profile.rank_level,
            completed_answers=int(completed_answers or 0),
            recent_attempts=len(recent_statuses),
            recent_completed_attempts=sum(status == "answered" for status in recent_statuses),
            recent_rated_answers=len(recent_ratings),
            recent_positive_answers=sum(value == "positive" for value in recent_ratings),
        )

    async def _locked_profile(self, user_id: UUID) -> HumanProfileModel | None:
        return await self._session.scalar(
            select(HumanProfileModel).where(HumanProfileModel.user_id == user_id).with_for_update()
        )

    async def _update_waiting_rank(self, user_id: UUID, rank_level: int) -> None:
        await self._session.execute(
            update(HumanWaitEntryModel)
            .where(
                HumanWaitEntryModel.performer_user_id == user_id,
                HumanWaitEntryModel.status == "waiting",
            )
            .values(rank_level=rank_level)
        )

    async def _lock_matching(self) -> None:
        await self._session.execute(select(func.pg_advisory_xact_lock(HUMAN_MATCH_LOCK_KEY)))

    @staticmethod
    def _empty_evidence() -> HumanRankEvidence:
        return HumanRankEvidence(
            rank_level=1,
            completed_answers=0,
            recent_attempts=0,
            recent_completed_attempts=0,
            recent_rated_answers=0,
            recent_positive_answers=0,
        )
