from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import get_session_factory
from app.domain.human_ranks import HUMAN_RANK_POLICY, HumanRankPolicy, HumanRankTrigger
from app.domain.principals import Principal
from app.domain.responses import ResponseEvaluation, ResponseEvaluationValue
from app.repositories.evaluations import ResponseEvaluationRepository
from app.repositories.human_ranks import SqlAlchemyHumanRankRepository


class ResponseEvaluationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        rank_policy: HumanRankPolicy = HUMAN_RANK_POLICY,
    ) -> None:
        self._session_factory = session_factory
        self._rank_policy = rank_policy

    async def set(
        self,
        principal: Principal,
        execution_id: UUID,
        value: ResponseEvaluationValue,
    ) -> ResponseEvaluation:
        async with self._session_factory() as session:
            evaluation = await ResponseEvaluationRepository(session).set(
                principal,
                execution_id,
                value,
            )
            await SqlAlchemyHumanRankRepository(
                session,
                policy=self._rank_policy,
            ).recalculate_for_execution(
                execution_id,
                HumanRankTrigger.EVALUATION_SET,
            )
            await session.commit()
        return evaluation

    async def clear(self, principal: Principal, execution_id: UUID) -> None:
        async with self._session_factory() as session:
            await ResponseEvaluationRepository(session).clear(
                principal,
                execution_id,
            )
            await SqlAlchemyHumanRankRepository(
                session,
                policy=self._rank_policy,
            ).recalculate_for_execution(
                execution_id,
                HumanRankTrigger.EVALUATION_CLEARED,
            )
            await session.commit()


@lru_cache
def get_response_evaluation_service() -> ResponseEvaluationService:
    return ResponseEvaluationService(get_session_factory())
