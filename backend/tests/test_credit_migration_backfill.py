import os

import pytest
from sqlalchemy import func, select

from app.db.session import dispose_engine, get_session_factory
from app.models.credits import InferenceBillingIntentModel
from app.models.platform import ActorModel, ExecutionModel, ResponseRequestModel

pytestmark = pytest.mark.skipif(
    os.getenv("SODAI_CREDIT_BACKFILL_TEST") != "1",
    reason="run after the credit migration round trip",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_every_preexisting_active_execution_received_a_free_intent() -> None:
    try:
        async with get_session_factory()() as session:
            missing = await session.scalar(
                select(func.count())
                .select_from(ExecutionModel)
                .outerjoin(
                    InferenceBillingIntentModel,
                    InferenceBillingIntentModel.execution_reference_id
                    == ExecutionModel.id,
                )
                .where(
                    ExecutionModel.status.in_(("queued", "running")),
                    InferenceBillingIntentModel.execution_reference_id.is_(None),
                )
            )
            metered = await session.scalar(
                select(func.count())
                .select_from(InferenceBillingIntentModel)
                .join(
                    ExecutionModel,
                    ExecutionModel.id
                    == InferenceBillingIntentModel.execution_reference_id,
                )
                .where(
                    ExecutionModel.status.in_(("queued", "running")),
                    InferenceBillingIntentModel.maximum_charge != 0,
                )
            )
            misattributed = await session.scalar(
                select(func.count())
                .select_from(InferenceBillingIntentModel)
                .join(
                    ExecutionModel,
                    ExecutionModel.id
                    == InferenceBillingIntentModel.execution_reference_id,
                )
                .join(
                    ResponseRequestModel,
                    ResponseRequestModel.id == ExecutionModel.response_request_id,
                )
                .join(
                    ActorModel,
                    ActorModel.id == ResponseRequestModel.requester_actor_id,
                )
                .where(
                    ExecutionModel.status.in_(("queued", "running")),
                    InferenceBillingIntentModel.user_id.is_distinct_from(
                        ActorModel.owner_user_id
                    ),
                )
            )
        assert missing == 0
        assert metered == 0
        assert misattributed == 0
    finally:
        await dispose_engine()
