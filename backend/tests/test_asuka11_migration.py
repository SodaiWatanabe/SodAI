import os
from uuid import UUID

import pytest
from sqlalchemy import select, text

from app.db.session import dispose_engine, get_session_factory
from app.models.platform import ActorModel, ThreadModel

MIGRATION_PHASE = os.getenv("SODAI_ASUKA11_MIGRATION_TEST")
USER_ID = UUID("00000000-0000-4000-8000-000000000181")
OWNER_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000182")
SPACE_ID = UUID("00000000-0000-4000-8000-000000000183")
THREAD_ID = UUID("00000000-0000-4000-8000-000000000184")

pytestmark = pytest.mark.skipif(
    MIGRATION_PHASE not in {"prepare", "verify"},
    reason="run around the Asuka 1.1 migration",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_asuka_1_1_upgrade_path() -> None:
    try:
        if MIGRATION_PHASE == "prepare":
            await prepare_asuka_1_thread()
        else:
            await verify_asuka_1_1_upgrade()
    finally:
        await dispose_engine()


async def prepare_asuka_1_thread() -> None:
    async with get_session_factory()() as session:
        await session.execute(
            text(
                """
                INSERT INTO app.users (id, display_name)
                VALUES (:user_id, 'asuka-migration-user')
                """
            ),
            {"user_id": USER_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO app.actors (id, kind, key, name, owner_user_id)
                VALUES (:actor_id, 'human', :actor_key, '対話相手', :user_id)
                """
            ),
            {
                "actor_id": OWNER_ACTOR_ID,
                "actor_key": f"human:{OWNER_ACTOR_ID}",
                "user_id": USER_ID,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO app.spaces (id, owner_user_id)
                VALUES (:space_id, :user_id)
                """
            ),
            {"space_id": SPACE_ID, "user_id": USER_ID},
        )
        await session.execute(
            text(
                """
                INSERT INTO app.space_memberships (space_id, actor_id, role)
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
                    'Asuka 1 migration thread', 'asuka-1', 1
                )
                """
            ),
            {
                "thread_id": THREAD_ID,
                "space_id": SPACE_ID,
                "actor_id": OWNER_ACTOR_ID,
            },
        )
        await session.commit()


async def verify_asuka_1_1_upgrade() -> None:
    async with get_session_factory()() as session:
        new_actor = await session.scalar(
            select(ActorModel).where(ActorModel.key == "model:asuka-1.1")
        )
        old_actor = await session.scalar(
            select(ActorModel).where(ActorModel.key == "model:asuka-1")
        )
        thread = await session.get(ThreadModel, THREAD_ID)

        assert new_actor is not None
        assert new_actor.name == "Asuka 1.1"
        assert old_actor is not None
        assert old_actor.name == "Asuka 1"
        assert thread is not None
        assert thread.default_answerer == "asuka-1.1"
