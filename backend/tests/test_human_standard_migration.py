import os
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId, get_answerer
from app.domain.principals import Principal, PrincipalKind
from app.models.account import UserModel
from app.models.humans import HumanTaskModel
from app.models.platform import ActorModel, ExecutionModel, ResponseRequestModel
from app.repositories.threads import SqlAlchemyThreadRepository

MIGRATION_PHASE = os.getenv("SODAI_HUMAN_STANDARD_MIGRATION_TEST")
SEED_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
STANDARD_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000005")

pytestmark = pytest.mark.skipif(
    MIGRATION_PHASE not in {"prepare", "verify"},
    reason="run around the Human Standard migration",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_human_standard_upgrade_path() -> None:
    try:
        if MIGRATION_PHASE == "prepare":
            await prepare_preexisting_pro_task()
        else:
            await verify_upgrade_and_cleanup()
    finally:
        await dispose_engine()


async def prepare_preexisting_pro_task() -> None:
    principal = Principal(PrincipalKind.USER, SEED_USER_ID)
    answerer = get_answerer(AnswererId.HUMAN_PRO)
    assert answerer is not None

    async with get_session_factory()() as session:
        session.add(UserModel(id=SEED_USER_ID, display_name="migration-user"))
        repository = SqlAlchemyThreadRepository(session)
        context = await repository.ensure_personal_context(principal)
        creation = await repository.create_thread_response(
            principal,
            context,
            "0005で作成済みのHuman Proタスク",
            answerer,
            execution_target="human:human-pro",
            artifact_id=None,
            deadline_at=None,
        )
        task = await session.get(HumanTaskModel, creation.response.execution.id)
        assert task is not None
        task.required_rank_level = 2
        await session.commit()


async def verify_upgrade_and_cleanup() -> None:
    async with get_session_factory()() as session:
        standard_actor = await session.scalar(
            select(ActorModel).where(ActorModel.key == "model:human-standard")
        )
        pro_rank = await session.scalar(
            select(HumanTaskModel.required_rank_level)
            .join(ExecutionModel, ExecutionModel.id == HumanTaskModel.execution_id)
            .join(
                ResponseRequestModel,
                ResponseRequestModel.id == ExecutionModel.response_request_id,
            )
            .where(ResponseRequestModel.requested_answerer == "human-pro")
        )
        assert standard_actor is not None
        assert standard_actor.id == STANDARD_ACTOR_ID
        assert pro_rank == 3

        owner_actor = await session.scalar(
            select(ActorModel).where(ActorModel.owner_user_id == SEED_USER_ID)
        )
        user = await session.get(UserModel, SEED_USER_ID)
        assert owner_actor is not None and user is not None
        await session.delete(user)
        await session.flush()
        await session.delete(owner_actor)
        await session.commit()
