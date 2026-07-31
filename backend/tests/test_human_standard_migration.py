import os
from uuid import UUID

import pytest
from sqlalchemy import select, text

from app.db.session import dispose_engine, get_session_factory
from app.models.account import UserModel
from app.models.humans import HumanTaskModel
from app.models.platform import ActorModel, ExecutionModel, ResponseRequestModel

MIGRATION_PHASE = os.getenv("SODAI_HUMAN_STANDARD_MIGRATION_TEST")
SEED_USER_ID = UUID("00000000-0000-4000-8000-000000000101")
OWNER_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000102")
SPACE_ID = UUID("00000000-0000-4000-8000-000000000103")
THREAD_ID = UUID("00000000-0000-4000-8000-000000000104")
ENTRY_ID = UUID("00000000-0000-4000-8000-000000000105")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000106")
EXECUTION_ID = UUID("00000000-0000-4000-8000-000000000107")
ATTEMPT_ID = UUID("00000000-0000-4000-8000-000000000108")
PRO_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000004")
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
    async with get_session_factory()() as session:
        # Historical migration fixtures use only columns present at 0005.
        # This keeps the migration test independent from future ORM tables.
        await session.execute(
            text(
                """
                INSERT INTO app.users (id, display_name)
                VALUES (:user_id, 'migration-user')
                """
            ),
            {"user_id": SEED_USER_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO app.actors (
                    id, kind, key, name, owner_user_id
                )
                VALUES (
                    :actor_id, 'human', :actor_key, '対話相手', :user_id
                )
                """
            ),
            {
                "actor_id": OWNER_ACTOR_ID,
                "actor_key": f"human:{OWNER_ACTOR_ID}",
                "user_id": SEED_USER_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO app.spaces (id, owner_user_id)
                VALUES (:space_id, :user_id)
                """
            ),
            {"space_id": SPACE_ID, "user_id": SEED_USER_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO app.space_memberships (
                    space_id, actor_id, role
                )
                VALUES (:space_id, :actor_id, 'owner')
                """
            ),
            {"space_id": SPACE_ID, "actor_id": OWNER_ACTOR_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO app.threads (
                    id, space_id, created_by_actor_id, title,
                    default_answerer, revision
                )
                VALUES (
                    :thread_id, :space_id, :actor_id,
                    '0005で作成済みのHuman Proタスク', 'human-pro', 1
                )
                """
            ),
            {
                "thread_id": THREAD_ID,
                "space_id": SPACE_ID,
                "actor_id": OWNER_ACTOR_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO app.thread_participants (
                    thread_id, actor_id, role
                )
                VALUES
                    (:thread_id, :owner_actor_id, 'participant'),
                    (:thread_id, :pro_actor_id, 'answerer')
                """
            ),
            {
                "thread_id": THREAD_ID,
                "owner_actor_id": OWNER_ACTOR_ID,
                "pro_actor_id": PRO_ACTOR_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO app.thread_entries (
                    id, thread_id, author_actor_id, ordinal
                )
                VALUES (:entry_id, :thread_id, :actor_id, 0)
                """
            ),
            {
                "entry_id": ENTRY_ID,
                "thread_id": THREAD_ID,
                "actor_id": OWNER_ACTOR_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO app.entry_text_contents (entry_id, content)
                VALUES (:entry_id, '0005で作成済みのHuman Proタスク')
                """
            ),
            {"entry_id": ENTRY_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO app.response_requests (
                    id, thread_id, requester_actor_id, target_actor_id,
                    input_entry_id, requested_answerer
                )
                VALUES (
                    :request_id, :thread_id, :owner_actor_id, :pro_actor_id,
                    :entry_id, 'human-pro'
                )
                """
            ),
            {
                "request_id": REQUEST_ID,
                "thread_id": THREAD_ID,
                "owner_actor_id": OWNER_ACTOR_ID,
                "pro_actor_id": PRO_ACTOR_ID,
                "entry_id": ENTRY_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO app.executions (
                    id, response_request_id, thread_id, target_actor_id,
                    attempt_id, execution_target
                )
                VALUES (
                    :execution_id, :request_id, :thread_id, :pro_actor_id,
                    :attempt_id, 'human:human-pro'
                )
                """
            ),
            {
                "execution_id": EXECUTION_ID,
                "request_id": REQUEST_ID,
                "thread_id": THREAD_ID,
                "pro_actor_id": PRO_ACTOR_ID,
                "attempt_id": ATTEMPT_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO app.human_tasks (
                    execution_id, required_rank_level
                )
                VALUES (:execution_id, 2)
                """
            ),
            {"execution_id": EXECUTION_ID},
        )
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
