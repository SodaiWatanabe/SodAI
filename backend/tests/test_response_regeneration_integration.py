import os
from uuid import uuid4

import pytest
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationPhase,
)
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId
from app.domain.human_answer_conditions import HumanAnswerConditions
from app.domain.principals import Principal, PrincipalKind
from app.domain.reasoning import ReasoningEffort
from app.models.account import UserModel
from app.models.platform import (
    ExecutionModel,
    ResponseContextItemModel,
    ResponseRequestModel,
    ThreadEntryModel,
)
from app.repositories.threads import SqlAlchemyThreadRepository
from app.services.human import HumanService
from app.services.inference.billing import InferenceBillingService
from app.services.inference.deployment import ModelDeploymentRegistry
from app.services.thread import ThreadService

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


async def create_user(name: str) -> Principal:
    principal = Principal(PrincipalKind.USER, uuid4())
    async with get_session_factory()() as session:
        session.add(UserModel(id=principal.id, display_name=name))
        await session.commit()
    return principal


def thread_service() -> ThreadService:
    settings = get_settings()
    return ThreadService(
        get_session_factory(),
        ModelDeploymentRegistry(settings.model_root),
        settings,
    )


async def complete_model_response(
    thread_id,
    execution_id,
    attempt_id,
    content: str,
) -> None:
    events = (
        GenerationEvent.create(
            GenerationEventType.STARTED,
            execution_id=execution_id,
            attempt_id=attempt_id,
            sequence=0,
            thread_id=thread_id,
            resolved_model="hina@2222222222222222",
            phase=GenerationPhase.ANSWERING,
        ),
        GenerationEvent.create(
            GenerationEventType.COMPLETED,
            execution_id=execution_id,
            attempt_id=attempt_id,
            sequence=1,
            thread_id=thread_id,
            content=content,
            thinking_content="",
            output_tokens=2,
            thinking_tokens=0,
            answer_tokens=1,
            finish_reason=FinishReason.STOP,
        ),
    )
    factory = get_session_factory()
    for event in events:
        async with factory() as session:
            await SqlAlchemyThreadRepository(session).project_generation_event(event)
            if event.type is GenerationEventType.COMPLETED:
                await InferenceBillingService(session).finalize(execution_id)
            await session.commit()


async def context_entry_ids(response_request_id):
    async with get_session_factory()() as session:
        return tuple(
            await session.scalars(
                select(ResponseContextItemModel.entry_id)
                .where(
                    ResponseContextItemModel.response_request_id
                    == response_request_id
                )
                .order_by(ResponseContextItemModel.ordinal)
            )
        )


@pytest.mark.anyio
async def test_ai_regeneration_preserves_context_and_replaces_only_the_projection() -> None:
    requester = await create_user("AI regeneration requester")
    service = thread_service()
    original = await service.create(requester, "同じ文脈で答えて", AnswererId.HINA)
    first_execution = original.response.execution
    await complete_model_response(
        original.thread.id,
        first_execution.id,
        first_execution.attempt_id,
        "最初のAI回答",
    )
    original_completed = await service.get(requester, original.thread.id)
    assert original_completed.latest_response is not None
    first_result_entry_id = (
        original_completed.latest_response.execution.result_entry_id
    )
    assert first_result_entry_id is not None

    regenerated = await service.regenerate(requester, original.response.id)
    replayed = await service.regenerate(requester, original.response.id)

    assert replayed.response.id == regenerated.response.id
    assert regenerated.response.id != original.response.id
    assert regenerated.response.input_entry_id == original.response.input_entry_id
    assert regenerated.response.requested_answerer is AnswererId.HINA
    assert await context_entry_ids(regenerated.response.id) == await context_entry_ids(
        original.response.id
    )
    assert [entry.content for entry in regenerated.thread.entries] == [
        "同じ文脈で答えて"
    ]

    async with get_session_factory()() as session:
        replacement = await session.get(ResponseRequestModel, regenerated.response.id)
        old_result = await session.get(ThreadEntryModel, first_result_entry_id)
        raw_entries = tuple(
            await session.scalars(
                select(ThreadEntryModel).where(
                    ThreadEntryModel.thread_id == original.thread.id
                )
            )
        )
    assert replacement is not None
    assert replacement.regenerated_from_response_request_id == original.response.id
    assert old_result is not None
    assert len(raw_entries) == 2

    next_execution = regenerated.response.execution
    await complete_model_response(
        regenerated.thread.id,
        next_execution.id,
        next_execution.attempt_id,
        "再生成したAI回答",
    )
    completed = await service.get(requester, regenerated.thread.id)
    assert completed.latest_response is not None
    next_result_entry_id = completed.latest_response.execution.result_entry_id
    assert next_result_entry_id is not None
    assert [entry.content for entry in completed.entries] == [
        "同じ文脈で答えて",
        "再生成したAI回答",
    ]

    follow_up = await service.append(
        requester,
        completed.id,
        "続けて",
        AnswererId.HINA,
    )
    follow_up_context = await context_entry_ids(follow_up.response.id)
    assert first_result_entry_id not in follow_up_context
    assert next_result_entry_id in follow_up_context

    old_search = await service.search(requester, "最初のAI回答", limit=20)
    new_search = await service.search(requester, "再生成したAI回答", limit=20)
    assert old_search.items == ()
    assert [item.thread.id for item in new_search.items] == [completed.id]
    await complete_model_response(
        follow_up.thread.id,
        follow_up.response.execution.id,
        follow_up.response.execution.attempt_id,
        "続きのAI回答",
    )


@pytest.mark.anyio
async def test_human_regeneration_uses_the_same_lineage_and_matching_flow() -> None:
    requester = await create_user("Human regeneration requester")
    performer = await create_user("Human regeneration performer")
    service = thread_service()
    human = HumanService(get_session_factory())
    original = await service.create(
        requester,
        "Humanとして答えて",
        AnswererId.HUMAN_LITE,
        ReasoningEffort.LOW,
    )
    await human.set_rank(performer.id, 1)
    first_assignment = await human.ready(
        performer.id,
        HumanAnswerConditions(
            answerer_ids=(AnswererId.HUMAN_LITE,),
            reasoning_efforts=(ReasoningEffort.LOW,),
        ),
    )
    assert first_assignment.assignment is not None
    await human.answer(
        performer.id,
        first_assignment.assignment.claim_id,
        "最初のHuman回答",
    )

    regenerated = await service.regenerate(requester, original.response.id)
    replayed = await service.regenerate(requester, original.response.id)
    assert replayed.response.id == regenerated.response.id
    assert regenerated.response.input_entry_id == original.response.input_entry_id
    assert regenerated.response.requested_answerer is AnswererId.HUMAN_LITE
    assert regenerated.response.reasoning_effort is ReasoningEffort.LOW
    assert [entry.content for entry in regenerated.thread.entries] == [
        "Humanとして答えて"
    ]
    assert await context_entry_ids(regenerated.response.id) == await context_entry_ids(
        original.response.id
    )

    second_assignment = await human.ready(
        performer.id,
        HumanAnswerConditions(
            answerer_ids=(AnswererId.HUMAN_LITE,),
            reasoning_efforts=(ReasoningEffort.LOW,),
        ),
    )
    assert second_assignment.assignment is not None
    assert (
        second_assignment.assignment.execution_id
        == regenerated.response.execution.id
    )
    await human.answer(
        performer.id,
        second_assignment.assignment.claim_id,
        "再生成したHuman回答",
    )

    completed = await service.get(requester, regenerated.thread.id)
    assert [entry.content for entry in completed.entries] == [
        "Humanとして答えて",
        "再生成したHuman回答",
    ]
    async with get_session_factory()() as session:
        original_execution = await session.get(
            ExecutionModel,
            original.response.execution.id,
        )
        replacement = await session.get(ResponseRequestModel, regenerated.response.id)
    assert original_execution is not None
    assert original_execution.result_entry_id is not None
    assert replacement is not None
    assert replacement.regenerated_from_response_request_id == original.response.id
