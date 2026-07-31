import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sodai_contracts.inference import FinishReason, GenerationEvent, GenerationEventType
from sqlalchemy import func, select

from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId, get_answerer
from app.domain.principals import Principal, PrincipalKind
from app.domain.responses import ResponseEvaluationValue
from app.models.platform import GuestSessionModel, ResponseEvaluationModel
from app.repositories.evaluations import (
    ResponseEvaluationNotFoundError,
    ResponseEvaluationNotReadyError,
)
from app.repositories.threads import SqlAlchemyThreadRepository
from app.services.evaluations import ResponseEvaluationService

pytestmark = pytest.mark.skipif(
    os.getenv("SODAI_INTEGRATION_TESTS") != "1",
    reason="set SODAI_INTEGRATION_TESTS=1 to run PostgreSQL integration tests",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def isolated_database_engine():
    yield
    await dispose_engine()


async def create_guest() -> Principal:
    principal = Principal(PrincipalKind.GUEST, uuid4())
    now = datetime.now(timezone.utc)
    async with get_session_factory()() as session:
        session.add(
            GuestSessionModel(
                id=principal.id,
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=now + timedelta(days=1),
                last_seen_at=now,
            )
        )
        await session.commit()
    return principal


async def delete_guest(principal: Principal) -> None:
    async with get_session_factory()() as session:
        guest = await session.get(GuestSessionModel, principal.id)
        if guest is not None:
            await session.delete(guest)
            await session.commit()


async def create_response(principal: Principal, content: str):
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyThreadRepository(session)
        context = await repository.ensure_personal_context(principal)
        creation = await repository.create_thread_response(
            principal,
            context,
            content,
            get_answerer(AnswererId.HINA),
            execution_target="local:hina",
            artifact_id="evaluation-integration",
            deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        await session.commit()
        return creation


async def complete_response(creation, content: str) -> None:
    execution = creation.response.execution
    events = (
        GenerationEvent.create(
            GenerationEventType.STARTED,
            execution_id=execution.id,
            attempt_id=execution.attempt_id,
            sequence=0,
            thread_id=creation.thread.id,
            resolved_model="hina@evaluation-integration",
        ),
        GenerationEvent.create(
            GenerationEventType.COMPLETED,
            execution_id=execution.id,
            attempt_id=execution.attempt_id,
            sequence=1,
            thread_id=creation.thread.id,
            content=content,
            finish_reason=FinishReason.STOP,
        ),
    )
    factory = get_session_factory()
    for event in events:
        async with factory() as session:
            await SqlAlchemyThreadRepository(session).project_generation_event(event)
            await session.commit()


@pytest.mark.anyio
async def test_requester_can_change_and_clear_own_completed_response_evaluation() -> None:
    requester = await create_guest()
    other = await create_guest()
    try:
        creation = await create_response(requester, "この回答を評価します")
        execution_id = creation.response.execution.id
        await complete_response(creation, "評価できる回答です。")

        service = ResponseEvaluationService(get_session_factory())
        positive = await service.set(
            requester,
            execution_id,
            ResponseEvaluationValue.POSITIVE,
        )
        assert positive.value is ResponseEvaluationValue.POSITIVE

        async with get_session_factory()() as session:
            thread = await SqlAlchemyThreadRepository(session).get(
                requester,
                creation.thread.id,
            )
            evaluation = await session.get(ResponseEvaluationModel, execution_id)

        result_entry = thread.entries[-1]
        assert result_entry.execution_id == execution_id
        assert result_entry.evaluation is ResponseEvaluationValue.POSITIVE
        assert thread.latest_response is not None
        assert (
            thread.latest_response.execution.evaluation
            is ResponseEvaluationValue.POSITIVE
        )
        assert evaluation is not None
        created_at = evaluation.created_at

        negative = await service.set(
            requester,
            execution_id,
            ResponseEvaluationValue.NEGATIVE,
        )
        assert negative.value is ResponseEvaluationValue.NEGATIVE
        assert negative.created_at == created_at

        async with get_session_factory()() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(ResponseEvaluationModel)
                .where(ResponseEvaluationModel.execution_id == execution_id)
            )
        assert count == 1

        with pytest.raises(ResponseEvaluationNotFoundError):
            await service.set(
                other,
                execution_id,
                ResponseEvaluationValue.POSITIVE,
            )
        with pytest.raises(ResponseEvaluationNotFoundError):
            await service.clear(other, execution_id)

        await service.clear(requester, execution_id)
        await service.clear(requester, execution_id)

        async with get_session_factory()() as session:
            thread = await SqlAlchemyThreadRepository(session).get(
                requester,
                creation.thread.id,
            )
            evaluation = await session.get(ResponseEvaluationModel, execution_id)

        assert thread.entries[-1].evaluation is None
        assert thread.latest_response is not None
        assert thread.latest_response.execution.evaluation is None
        assert evaluation is None
    finally:
        await delete_guest(requester)
        await delete_guest(other)


@pytest.mark.anyio
async def test_incomplete_response_cannot_be_evaluated_or_cleared() -> None:
    requester = await create_guest()
    try:
        creation = await create_response(requester, "まだ回答されていません")
        execution_id = creation.response.execution.id
        service = ResponseEvaluationService(get_session_factory())

        with pytest.raises(ResponseEvaluationNotReadyError):
            await service.set(
                requester,
                execution_id,
                ResponseEvaluationValue.POSITIVE,
            )
        with pytest.raises(ResponseEvaluationNotReadyError):
            await service.clear(requester, execution_id)
    finally:
        await delete_guest(requester)
