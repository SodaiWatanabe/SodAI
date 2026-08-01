from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session_factory
from app.domain.human_answer_conditions import HumanAnswerConditions
from app.domain.human_ranks import (
    HUMAN_RANK_POLICY,
    HumanRankPolicy,
    HumanRankTrigger,
)
from app.domain.humans import BrainState
from app.domain.principals import Principal, PrincipalKind
from app.repositories.human_ranks import SqlAlchemyHumanRankRepository
from app.repositories.humans import HumanProjection, SqlAlchemyHumanRepository
from app.services.human_credits import HumanCreditService
from app.services.realtime import realtime_hub

logger = logging.getLogger(__name__)


class HumanService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        rank_policy: HumanRankPolicy = HUMAN_RANK_POLICY,
    ) -> None:
        self._session_factory = session_factory
        self._rank_policy = rank_policy

    async def state(self, user_id: UUID) -> BrainState:
        async with self._session_factory() as session:
            return await SqlAlchemyHumanRepository(session).state(user_id)

    async def ready(
        self,
        user_id: UUID,
        answer_conditions: HumanAnswerConditions | None = None,
    ) -> BrainState:
        async with self._session_factory() as session:
            await SqlAlchemyHumanRepository(session).ready(user_id, answer_conditions)
            await session.commit()
        await self.match_available_best_effort()
        return await self.state(user_id)

    async def set_rank(self, user_id: UUID, rank_level: int) -> BrainState:
        async with self._session_factory() as session:
            await SqlAlchemyHumanRankRepository(
                session,
                policy=self._rank_policy,
            ).set_manual_rank(user_id, rank_level)
            await session.commit()
        await self.match_available_best_effort()
        return await self.state(user_id)

    async def stop(self, user_id: UUID) -> BrainState:
        async with self._session_factory() as session:
            state = await SqlAlchemyHumanRepository(session).stop(user_id)
            await session.commit()
            return state

    async def skip(self, user_id: UUID, claim_id: UUID) -> BrainState:
        return await self._release_assignment(user_id, claim_id, outcome="skipped")

    async def decline(self, user_id: UUID, claim_id: UUID) -> BrainState:
        return await self._release_assignment(user_id, claim_id, outcome="declined")

    async def _release_assignment(
        self,
        user_id: UUID,
        claim_id: UUID,
        *,
        outcome: Literal["skipped", "declined"],
    ) -> BrainState:
        async with self._session_factory() as session:
            repository = SqlAlchemyHumanRepository(session)
            projection = (
                await repository.skip(user_id, claim_id)
                if outcome == "skipped"
                else await repository.decline(user_id, claim_id)
            )
            await session.commit()
        await self._publish_owner(projection, "response.queued", {})
        await self.match_available_best_effort()
        return await self.state(user_id)

    async def save_draft(
        self,
        user_id: UUID,
        claim_id: UUID,
        content: str,
        revision: int,
    ) -> int:
        async with self._session_factory() as session:
            saved_revision = await SqlAlchemyHumanRepository(session).save_draft(
                user_id,
                claim_id,
                content,
                revision,
            )
            await session.commit()
        return saved_revision

    async def answer(self, user_id: UUID, claim_id: UUID, content: str) -> BrainState:
        async with self._session_factory() as session:
            repository = SqlAlchemyHumanRepository(session)
            projection = await repository.answer(user_id, claim_id, content.strip())
            await HumanCreditService(session).settle_answer(
                projection.execution_id,
                user_id,
            )
            await SqlAlchemyHumanRankRepository(
                session,
                policy=self._rank_policy,
            ).recalculate(
                user_id,
                HumanRankTrigger.ANSWER_COMPLETED,
                trigger_execution_id=projection.execution_id,
            )
            await session.commit()
        await self._publish_owner(
            projection,
            "response.completed",
            {
                "target_actor_id": str(projection.target_actor_id),
                "result_entry_id": (
                    str(projection.result_entry_id) if projection.result_entry_id else None
                ),
                "content": content.strip(),
            },
        )
        await self.match_available_best_effort()
        return await self.state(user_id)

    async def match_available_best_effort(self) -> None:
        try:
            await self.match_available()
        except Exception:
            logger.exception("Human matching failed after transaction commit")

    async def match_available(self) -> None:
        while True:
            async with self._session_factory() as session:
                result = await SqlAlchemyHumanRepository(session).match_once()
                credit_service = HumanCreditService(session)
                rank_repository = SqlAlchemyHumanRankRepository(
                    session,
                    policy=self._rank_policy,
                )
                for auto_answer in result.auto_answered:
                    performer_user_id = auto_answer.projection.performer_user_id
                    if performer_user_id is None:
                        raise RuntimeError("automatic Human answer is missing its performer")
                    await credit_service.settle_answer(
                        auto_answer.projection.execution_id,
                        performer_user_id,
                    )
                    await rank_repository.recalculate(
                        performer_user_id,
                        HumanRankTrigger.ANSWER_COMPLETED,
                        trigger_execution_id=auto_answer.projection.execution_id,
                    )
                for projection in result.expired:
                    if projection.performer_user_id is None:
                        continue
                    await rank_repository.recalculate(
                        projection.performer_user_id,
                        HumanRankTrigger.ANSWER_EXPIRED,
                        trigger_execution_id=projection.execution_id,
                    )
                await session.commit()
            for auto_answer in result.auto_answered:
                projection = auto_answer.projection
                await self._publish_owner(
                    projection,
                    "response.completed",
                    {
                        "target_actor_id": str(projection.target_actor_id),
                        "result_entry_id": (
                            str(projection.result_entry_id)
                            if projection.result_entry_id
                            else None
                        ),
                        "content": auto_answer.content,
                    },
                )
                if projection.performer_user_id is not None and projection.claim_id is not None:
                    await realtime_hub.publish(
                        Principal(PrincipalKind.USER, projection.performer_user_id),
                        event_type="human.answer.auto_submitted",
                        space_id=projection.space_id,
                        thread_id=projection.thread_id,
                        thread_revision=projection.thread_revision,
                        response_request_id=projection.response_request_id,
                        execution_id=projection.execution_id,
                        data={"claim_id": str(projection.claim_id)},
                    )
            for projection in result.expired:
                await self._publish_owner(projection, "response.queued", {})
                if projection.performer_user_id is not None and projection.claim_id is not None:
                    await realtime_hub.publish(
                        Principal(PrincipalKind.USER, projection.performer_user_id),
                        event_type="human.assignment.cancelled",
                        space_id=projection.space_id,
                        thread_id=projection.thread_id,
                        thread_revision=projection.thread_revision,
                        response_request_id=projection.response_request_id,
                        execution_id=projection.execution_id,
                        data={
                            "claim_id": str(projection.claim_id),
                            "reason": (
                                projection.cancellation_reason or "assignment_expired"
                            ),
                        },
                    )
            if result.matched is None:
                return
            projection = result.matched
            await self._publish_owner(
                projection,
                "response.started",
                {"target_actor_id": str(projection.target_actor_id)},
            )
            if projection.performer_user_id is not None:
                await realtime_hub.publish(
                    Principal(PrincipalKind.USER, projection.performer_user_id),
                    event_type="human.assigned",
                    space_id=projection.space_id,
                    thread_id=projection.thread_id,
                    thread_revision=projection.thread_revision,
                    response_request_id=projection.response_request_id,
                    execution_id=projection.execution_id,
                    data={"claim_id": str(projection.claim_id)},
                )

    @staticmethod
    async def _publish_owner(
        projection: HumanProjection,
        event_type: str,
        data: dict[str, object],
    ) -> None:
        await realtime_hub.publish(
            Principal(PrincipalKind.USER, projection.owner_user_id),
            event_type=event_type,
            space_id=projection.space_id,
            thread_id=projection.thread_id,
            thread_revision=projection.thread_revision,
            response_request_id=projection.response_request_id,
            execution_id=projection.execution_id,
            data=data,
        )


@lru_cache
def get_human_service_singleton() -> HumanService:
    return HumanService(get_session_factory())


def get_human_service() -> HumanService:
    return get_human_service_singleton()
