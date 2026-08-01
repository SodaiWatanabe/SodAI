import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sodai_contracts.inference import GenerationEvent, GenerationEventType
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId, get_answerer
from app.domain.execution_events import EventDisposition
from app.domain.humans import HUMAN_SKIP_WINDOW
from app.domain.principals import Principal, PrincipalKind
from app.domain.reasoning import ReasoningEffort
from app.domain.threads import ActorKind
from app.models.account import UserModel
from app.models.humans import (
    HumanClaimModel,
    HumanProfileModel,
    HumanTaskModel,
    HumanWaitEntryModel,
)
from app.models.platform import (
    ActorModel,
    ExecutionModel,
    ModelExecutionModel,
    ResponseRequestModel,
    ThreadModel,
)
from app.repositories.human_answers import HumanAnswerNotFoundError
from app.repositories.humans import (
    HumanClaimNotFoundError,
    HumanClaimSkipWindowClosedError,
    SqlAlchemyHumanRepository,
)
from app.repositories.inference_operations import InferenceOperationsRepository
from app.repositories.response_completion import complete_response
from app.repositories.threads import (
    ExecutionNotFoundError,
    SqlAlchemyThreadRepository,
    ThreadNotFoundError,
)
from app.services.human import HumanService
from app.services.human_answers import HumanAnswerHistoryService

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


def principal() -> Principal:
    return Principal(PrincipalKind.USER, uuid4())


async def create_task(
    owner: Principal,
    answerer_id: AnswererId,
    content: str,
    reasoning_effort: ReasoningEffort | None = None,
) -> tuple[UUID, UUID]:
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyThreadRepository(session)
        context = await repository.ensure_personal_context(owner)
        creation = await repository.create_thread_response(
            owner,
            context,
            content,
            get_answerer(answerer_id),
            execution_target=f"human:{answerer_id.value}",
            artifact_id=None,
            deadline_at=None,
            reasoning_effort=reasoning_effort,
        )
        await session.commit()
    return creation.thread.id, creation.response.execution.id


@pytest.mark.anyio
async def test_reasoning_effort_sets_human_deadline_when_matching_starts() -> None:
    owner = principal()
    performer = principal()
    users = [owner, performer]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}")
            for index, item in enumerate(users)
        )
        await session.commit()

    expected_seconds = {
        ReasoningEffort.LOW: 120,
        ReasoningEffort.MEDIUM: 300,
        ReasoningEffort.HIGH: 1200,
        ReasoningEffort.XHIGH: 3600,
    }
    try:
        await human.set_rank(performer.id, 3)
        for effort, seconds in expected_seconds.items():
            await create_task(
                owner,
                AnswererId.HUMAN_PRO,
                f"{effort.value}の期限を検証するPrompt",
                effort,
            )
            assigned = await human.ready(performer.id)
            assert assigned.assignment is not None
            assert assigned.assignment.reasoning_effort is effort

            async with factory() as session:
                execution = await session.get(
                    ExecutionModel,
                    assigned.assignment.execution_id,
                )
            assert execution is not None
            assert execution.started_at is not None
            assert execution.deadline_at is not None
            assert (
                execution.deadline_at - execution.started_at
            ).total_seconds() == seconds
            assert assigned.assignment.deadline_at == execution.deadline_at

            await human.answer(
                performer.id,
                assigned.assignment.claim_id,
                f"{effort.value}の回答",
            )
    finally:
        await delete_users([item.id for item in users])


async def create_contextual_task(owner: Principal) -> tuple[UUID, UUID]:
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        repository = SqlAlchemyThreadRepository(session)
        context = await repository.ensure_personal_context(owner)
        first = await repository.create_thread_response(
            owner,
            context,
            "最初の質問",
            get_answerer(AnswererId.HINA),
            execution_target="local:hina",
            artifact_id="integration",
            deadline_at=now + timedelta(minutes=5),
        )
        execution = await session.get(ExecutionModel, first.response.execution.id)
        request = await session.get(ResponseRequestModel, first.response.id)
        thread = await session.get(ThreadModel, first.thread.id)
        assert execution is not None and request is not None and thread is not None
        execution.status = "running"
        execution.started_at = now
        execution.lease_expires_at = now + timedelta(minutes=1)
        request.status = "running"
        request.started_at = now
        await complete_response(
            session,
            execution,
            request,
            thread,
            "AIの回答",
            now,
        )
        human = await repository.append_response(
            owner,
            first.thread.id,
            context.actor.id,
            "Liteでも回答できるPrompt",
            get_answerer(AnswererId.HUMAN_LITE),
            execution_target="human:human-lite",
            artifact_id=None,
            deadline_at=None,
            model_limit=32,
            guest_model_limit=1,
        )
        await session.commit()
    return human.thread.id, human.response.execution.id


async def delete_users(user_ids: list[UUID]) -> None:
    factory = get_session_factory()
    async with factory() as session:
        actors = (
            await session.scalars(select(ActorModel).where(ActorModel.owner_user_id.in_(user_ids)))
        ).all()
        for user_id in user_ids:
            user = await session.get(UserModel, user_id)
            if user is not None:
                await session.delete(user)
        await session.flush()
        for actor in actors:
            await session.delete(actor)
        await session.commit()


@pytest.mark.anyio
async def test_claim_performer_must_own_the_wait_entry() -> None:
    owner = principal()
    performer = principal()
    other_performer = principal()
    users = [owner, performer, other_performer]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}") for index, item in enumerate(users)
        )
        await session.commit()

    try:
        await create_task(owner, AnswererId.HUMAN_LITE, "Claim所有者を検証するPrompt")
        assigned = await human.ready(performer.id)
        assert assigned.assignment is not None

        async with factory() as session:
            claim = await session.get(HumanClaimModel, assigned.assignment.claim_id)
            assert claim is not None
            claim.performer_user_id = other_performer.id
            with pytest.raises(IntegrityError) as error:
                await session.flush()
            assert "fk_human_claims_wait_entry_performer" in str(error.value.orig)
            await session.rollback()

        async with factory() as session:
            claim = await session.get(HumanClaimModel, assigned.assignment.claim_id)
        assert claim is not None
        assert claim.performer_user_id == performer.id
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_requester_cancellation_closes_human_claim_and_requeues_performer() -> None:
    owner = principal()
    performer = principal()
    users = [owner, performer]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}")
            for index, item in enumerate(users)
        )
        await session.commit()

    try:
        _, execution_id = await create_task(
            owner,
            AnswererId.HUMAN_LITE,
            "取消境界を検証するPrompt",
        )
        assigned = await human.ready(performer.id)
        assert assigned.assignment is not None
        claim_id = assigned.assignment.claim_id

        async with factory() as session:
            with pytest.raises(ExecutionNotFoundError):
                await SqlAlchemyThreadRepository(session).cancel_execution(
                    performer,
                    execution_id,
                )

        async with factory() as session:
            cancellation = await SqlAlchemyThreadRepository(session).cancel_execution(
                owner,
                execution_id,
            )
            await session.commit()
        assert cancellation.projection is not None
        assert cancellation.human_claim is not None
        assert cancellation.human_claim.claim_id == claim_id
        assert cancellation.human_claim.performer_user_id == performer.id
        assert cancellation.thread.latest_response is not None
        assert cancellation.thread.latest_response.status.value == "cancelled"

        async with factory() as session:
            replay = await SqlAlchemyThreadRepository(session).cancel_execution(
                owner,
                execution_id,
            )
            claim = await session.get(HumanClaimModel, claim_id)
            execution = await session.get(ExecutionModel, execution_id)
            waiting = await session.scalar(
                select(HumanWaitEntryModel).where(
                    HumanWaitEntryModel.performer_user_id == performer.id,
                    HumanWaitEntryModel.status == "waiting",
                )
            )
            await session.commit()
        assert replay.projection is None
        assert claim is not None and claim.status == "cancelled"
        assert execution is not None and execution.status == "cancelled"
        assert waiting is not None

        with pytest.raises(HumanClaimNotFoundError):
            await human.answer(performer.id, claim_id, "取消後の回答")
        state = await human.state(performer.id)
        assert state.status.value == "waiting"
        assert state.assignment is None
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_human_answer_and_requester_cancellation_have_one_winner() -> None:
    owner = principal()
    performer = principal()
    users = [owner, performer]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}")
            for index, item in enumerate(users)
        )
        await session.commit()

    try:
        thread_id, execution_id = await create_task(
            owner,
            AnswererId.HUMAN_LITE,
            "回答と取消の競合を検証するPrompt",
        )
        assigned = await human.ready(performer.id)
        assert assigned.assignment is not None
        claim_id = assigned.assignment.claim_id

        async def answer_once() -> bool:
            async with factory() as session:
                try:
                    await SqlAlchemyHumanRepository(session).answer(
                        performer.id,
                        claim_id,
                        "競合に勝ったHuman回答",
                    )
                except HumanClaimNotFoundError:
                    return False
                await session.commit()
                return True

        async def cancel_once() -> bool:
            async with factory() as session:
                result = await SqlAlchemyThreadRepository(session).cancel_execution(
                    owner,
                    execution_id,
                )
                await session.commit()
                return result.projection is not None

        answered, cancelled = await asyncio.wait_for(
            asyncio.gather(answer_once(), cancel_once()),
            timeout=5,
        )
        assert answered is not cancelled

        async with factory() as session:
            thread = await SqlAlchemyThreadRepository(session).get(owner, thread_id)
            claim = await session.get(HumanClaimModel, claim_id)
            waiting_count = await session.scalar(
                select(func.count())
                .select_from(HumanWaitEntryModel)
                .where(
                    HumanWaitEntryModel.performer_user_id == performer.id,
                    HumanWaitEntryModel.status == "waiting",
                )
            )
        assert thread.latest_response is not None
        assert claim is not None
        assert waiting_count == 1
        if answered:
            assert thread.latest_response.status.value == "completed"
            assert claim.status == "answered"
            assert [entry.content for entry in thread.entries][-1] == "競合に勝ったHuman回答"
        else:
            assert thread.latest_response.status.value == "cancelled"
            assert claim.status == "cancelled"
            assert len(thread.entries) == 1
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_generation_events_ignore_human_executions() -> None:
    owner = principal()
    factory = get_session_factory()

    async with factory() as session:
        session.add(UserModel(id=owner.id, display_name="owner"))
        await session.commit()

    try:
        thread_id, execution_id = await create_task(
            owner,
            AnswererId.HUMAN_LITE,
            "Generation Event境界を検証するPrompt",
        )
        async with factory() as session:
            execution = await session.get(ExecutionModel, execution_id)
            assert execution is not None
            request = await session.get(ResponseRequestModel, execution.response_request_id)
            thread = await session.get(ThreadModel, thread_id)
            assert request is not None
            assert thread is not None
            initial_execution = (
                execution.status,
                execution.started_at,
                execution.finished_at,
                execution.lease_expires_at,
                execution.error_code,
                execution.last_event_sequence,
                execution.last_event_id,
                execution.last_event_type,
            )
            initial_request = (request.status, request.started_at, request.finished_at)
            initial_thread_revision = thread.revision
            attempt_id = execution.attempt_id

        events = (
            GenerationEvent.create(
                GenerationEventType.STARTED,
                execution_id=execution_id,
                attempt_id=attempt_id,
                sequence=0,
                thread_id=thread_id,
                resolved_model="invalid-for-human",
            ),
            GenerationEvent.create(
                GenerationEventType.FAILED,
                execution_id=execution_id,
                attempt_id=attempt_id,
                sequence=0,
                thread_id=thread_id,
                error_code="invalid_for_human",
            ),
        )
        for event in events:
            async with factory() as session:
                result = await SqlAlchemyThreadRepository(session).project_generation_event(event)
                await session.commit()
            assert result.disposition is EventDisposition.IGNORE
            assert result.projection is None

        async with factory() as session:
            execution = await session.get(ExecutionModel, execution_id)
            assert execution is not None
            request = await session.get(ResponseRequestModel, execution.response_request_id)
            thread = await session.get(ThreadModel, thread_id)
        assert request is not None
        assert thread is not None
        assert (
            execution.status,
            execution.started_at,
            execution.finished_at,
            execution.lease_expires_at,
            execution.error_code,
            execution.last_event_sequence,
            execution.last_event_id,
            execution.last_event_type,
        ) == initial_execution
        assert (request.status, request.started_at, request.finished_at) == initial_request
        assert thread.revision == initial_thread_revision
    finally:
        await delete_users([owner.id])


@pytest.mark.anyio
async def test_human_matching_uses_oldest_compatible_task_and_returns_answer() -> None:
    junior = principal()
    senior = principal()
    second_senior = principal()
    standard_performer = principal()
    pro_owner = principal()
    standard_owner = principal()
    lite_owner = principal()
    users = [
        junior,
        senior,
        second_senior,
        standard_performer,
        pro_owner,
        standard_owner,
        lite_owner,
    ]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}") for index, item in enumerate(users)
        )
        await session.commit()

    try:
        self_thread_id, self_execution_id = await create_task(
            junior, AnswererId.HUMAN_LITE, "自分では回答できないPrompt"
        )
        pro_thread_id, pro_execution_id = await create_task(
            pro_owner, AnswererId.HUMAN_PRO, "Proだけが回答できるPrompt"
        )
        standard_thread_id, standard_execution_id = await create_task(
            standard_owner,
            AnswererId.HUMAN_STANDARD,
            "Standard以上が回答できるPrompt",
        )
        lite_thread_id, lite_execution_id = await create_contextual_task(lite_owner)
        base = datetime.now(timezone.utc) - timedelta(minutes=1)
        async with factory() as session:
            for offset, execution_id in enumerate(
                [
                    self_execution_id,
                    pro_execution_id,
                    standard_execution_id,
                    lite_execution_id,
                ]
            ):
                task = await session.get(HumanTaskModel, execution_id)
                assert task is not None, f"missing HumanTask for {execution_id}"
                task.queued_at = base + timedelta(seconds=offset)
            await session.commit()
        await human.set_rank(senior.id, 2)
        await human.set_rank(second_senior.id, 3)
        await human.set_rank(standard_performer.id, 2)

        junior_state = await human.ready(junior.id)
        assert junior_state.rank_name == "Human Lite"
        assert junior_state.assignment is not None
        assert junior_state.assignment.execution_id == lite_execution_id
        assert [entry.content for entry in junior_state.assignment.context] == [
            "最初の質問",
            "AIの回答",
            "Liteでも回答できるPrompt",
        ]
        assert [entry.author_kind for entry in junior_state.assignment.context] == [
            ActorKind.HUMAN,
            ActorKind.MODEL,
            ActorKind.HUMAN,
        ]

        senior_state = await human.ready(senior.id)
        assert senior_state.rank_name == "Human Standard"
        assert senior_state.assignment is not None
        assert senior_state.assignment.execution_id == self_execution_id

        standard_state = await human.ready(standard_performer.id)
        assert standard_state.rank_name == "Human Standard"
        assert standard_state.assignment is not None
        assert standard_state.assignment.execution_id == standard_execution_id

        second_senior_state = await human.ready(second_senior.id)
        assert second_senior_state.rank_name == "Human Pro"
        assert second_senior_state.assignment is not None
        assert second_senior_state.assignment.execution_id == pro_execution_id

        answered_state = await human.answer(
            junior.id,
            junior_state.assignment.claim_id,
            "Human Liteからの回答です。",
        )
        assert answered_state.status.value == "waiting"
        async with factory() as session:
            thread = await SqlAlchemyThreadRepository(session).get(lite_owner, lite_thread_id)
            human_task = await session.get(HumanTaskModel, lite_execution_id)
            model_execution = await session.get(ModelExecutionModel, lite_execution_id)
            model_expirations = await SqlAlchemyThreadRepository(session).expire_executions(
                datetime.now(timezone.utc) + timedelta(days=365)
            )
        assert [entry.content for entry in thread.entries] == [
            "最初の質問",
            "AIの回答",
            "Liteでも回答できるPrompt",
            "Human Liteからの回答です。",
        ]
        assert thread.entries[-1].author.key == "model:human-lite"
        assert thread.entries[-1].answerer is AnswererId.HUMAN_LITE
        assert thread.latest_response is not None
        assert thread.latest_response.status.value == "completed"
        assert human_task is not None
        assert model_execution is None
        assert model_expirations == []

        standard_answered_state = await human.answer(
            standard_performer.id,
            standard_state.assignment.claim_id,
            "Human Standardからの回答です。",
        )
        assert standard_answered_state.status.value == "waiting"
        async with factory() as session:
            standard_thread = await SqlAlchemyThreadRepository(session).get(
                standard_owner,
                standard_thread_id,
            )
        assert standard_thread.entries[-1].author.key == "model:human-standard"
        assert standard_thread.entries[-1].answerer is AnswererId.HUMAN_STANDARD

        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            owner_actor = await session.scalar(
                select(ActorModel).where(ActorModel.owner_user_id == lite_owner.id)
            )
            assert owner_actor is not None
            switched = await repository.append_response(
                lite_owner,
                lite_thread_id,
                owner_actor.id,
                "次はAIへ切り替える",
                get_answerer(AnswererId.HINA),
                execution_target="local:hina",
                artifact_id="integration",
                deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                model_limit=32,
                guest_model_limit=1,
            )
            switched_model = await session.get(ModelExecutionModel, switched.response.execution.id)
            switched_human = await session.get(HumanTaskModel, switched.response.execution.id)
            await session.commit()
        assert switched_model is not None
        assert switched_human is None

        history = HumanAnswerHistoryService(factory)
        history_page = await history.page(junior.id)
        assert [item.execution_id for item in history_page.items] == [
            lite_execution_id
        ]
        assert history_page.items[0].prompt_preview == "Liteでも回答できるPrompt"
        assert history_page.items[0].answerer_name == "Human Lite"
        history_detail = await history.get(junior.id, lite_execution_id)
        assert [entry.content for entry in history_detail.context] == [
            "最初の質問",
            "AIの回答",
            "Liteでも回答できるPrompt",
        ]
        assert history_detail.answer == "Human Liteからの回答です。"
        with pytest.raises(HumanAnswerNotFoundError):
            await history.get(lite_owner.id, lite_execution_id)

        skipped_state = await human.skip(
            second_senior.id,
            second_senior_state.assignment.claim_id,
        )
        assert skipped_state.status.value == "waiting"
        async with factory() as session:
            execution = await session.get(ExecutionModel, pro_execution_id)
            skipped_claim = await session.get(
                HumanClaimModel, second_senior_state.assignment.claim_id
            )
            inference = await InferenceOperationsRepository(session).snapshot()
        assert execution is not None and execution.status == "queued"
        assert skipped_claim is not None and skipped_claim.status == "skipped"
        assert inference.queued == 1
        assert inference.active_by_answerer == {AnswererId.HINA: 1}

        # The assigned Human is not a normal member of the owner's thread.
        async with factory() as session:
            with pytest.raises(ThreadNotFoundError):
                await SqlAlchemyThreadRepository(session).get(junior, lite_thread_id)
        assert self_thread_id != pro_thread_id
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_readiness_renews_an_active_assignment_without_rejoining_wait_queue() -> None:
    performer = principal()
    owner = principal()
    users = [performer, owner]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}") for index, item in enumerate(users)
        )
        await session.commit()

    try:
        await create_task(owner, AnswererId.HUMAN_LITE, "leaseを更新するPrompt")
        assigned = await human.ready(performer.id)
        assert assigned.assignment is not None

        expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        async with factory() as session:
            claim = await session.get(HumanClaimModel, assigned.assignment.claim_id)
            execution = await session.get(ExecutionModel, assigned.assignment.execution_id)
            assert claim is not None
            assert execution is not None
            claim.lease_expires_at = expired_at
            execution.lease_expires_at = expired_at
            await session.commit()

        renewed_at = datetime.now(timezone.utc)
        renewed = await human.ready(performer.id)
        assert renewed.assignment is not None
        assert renewed.assignment.claim_id == assigned.assignment.claim_id

        async with factory() as session:
            claim = await session.get(HumanClaimModel, assigned.assignment.claim_id)
            execution = await session.get(ExecutionModel, assigned.assignment.execution_id)
            waiting_entries = await session.scalar(
                select(func.count())
                .select_from(HumanWaitEntryModel)
                .where(
                    HumanWaitEntryModel.performer_user_id == performer.id,
                    HumanWaitEntryModel.status == "waiting",
                )
            )
        assert claim is not None
        assert execution is not None
        assert claim.lease_expires_at > renewed_at
        assert execution.lease_expires_at > renewed_at
        assert waiting_entries == 0
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_reasoning_deadline_expires_claim_and_requeues_task() -> None:
    owner = principal()
    first = principal()
    second = principal()
    users = [owner, first, second]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}")
            for index, item in enumerate(users)
        )
        await session.commit()

    try:
        _, execution_id = await create_task(
            owner,
            AnswererId.HUMAN_LITE,
            "回答期限を検証するPrompt",
            ReasoningEffort.LOW,
        )
        first_assignment = await human.ready(first.id)
        assert first_assignment.assignment is not None

        async with factory() as session:
            execution = await session.get(ExecutionModel, execution_id)
            assert execution is not None
            execution.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()

        second_assignment = await human.ready(second.id)
        assert second_assignment.assignment is not None
        assert second_assignment.assignment.execution_id == execution_id
        assert second_assignment.assignment.claim_id != first_assignment.assignment.claim_id

        with pytest.raises(HumanClaimNotFoundError):
            await human.answer(
                first.id,
                first_assignment.assignment.claim_id,
                "期限後の回答",
            )

        async with factory() as session:
            expired_claim = await session.get(
                HumanClaimModel,
                first_assignment.assignment.claim_id,
            )
        assert expired_claim is not None
        assert expired_claim.status == "expired"
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_skip_is_rejected_twenty_seconds_after_assignment() -> None:
    owner = principal()
    performer = principal()
    users = [owner, performer]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}")
            for index, item in enumerate(users)
        )
        await session.commit()

    try:
        _, execution_id = await create_task(
            owner,
            AnswererId.HUMAN_LITE,
            "スキップ猶予を検証するPrompt",
        )
        assigned = await human.ready(performer.id)
        assert assigned.assignment is not None
        claim_id = assigned.assignment.claim_id

        async with factory() as session:
            claim = await session.get(HumanClaimModel, claim_id)
            assert claim is not None
            assert assigned.assignment.skip_allowed_until == (
                claim.claimed_at + HUMAN_SKIP_WINDOW
            )
            claim.claimed_at = datetime.now(timezone.utc) - HUMAN_SKIP_WINDOW
            await session.commit()

        with pytest.raises(HumanClaimSkipWindowClosedError):
            await human.skip(performer.id, claim_id)

        async with factory() as session:
            claim = await session.get(HumanClaimModel, claim_id)
            execution = await session.get(ExecutionModel, execution_id)
        assert claim is not None and claim.status == "active"
        assert execution is not None and execution.status == "running"

        answered = await human.answer(performer.id, claim_id, "猶予後も回答はできます。")
        assert answered.status.value == "waiting"
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_expired_waiter_rejoins_at_the_end_of_the_queue() -> None:
    owner = principal()
    expired_waiter = principal()
    active_waiter = principal()
    users = [owner, expired_waiter, active_waiter]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}") for index, item in enumerate(users)
        )
        await session.commit()

    try:
        assert (await human.ready(expired_waiter.id)).status.value == "waiting"
        assert (await human.ready(active_waiter.id)).status.value == "waiting"

        async with factory() as session:
            expired_entry = await session.scalar(
                select(HumanWaitEntryModel).where(
                    HumanWaitEntryModel.performer_user_id == expired_waiter.id,
                    HumanWaitEntryModel.status == "waiting",
                )
            )
            assert expired_entry is not None
            expired_entry.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=31)
            await session.commit()

        assert (await human.ready(expired_waiter.id)).status.value == "waiting"

        async with factory() as session:
            expired_waiter_entries = (
                await session.scalars(
                    select(HumanWaitEntryModel)
                    .where(HumanWaitEntryModel.performer_user_id == expired_waiter.id)
                    .order_by(HumanWaitEntryModel.ready_at)
                )
            ).all()
            active_entry = await session.scalar(
                select(HumanWaitEntryModel).where(
                    HumanWaitEntryModel.performer_user_id == active_waiter.id,
                    HumanWaitEntryModel.status == "waiting",
                )
            )
        assert [entry.status for entry in expired_waiter_entries] == ["stale", "waiting"]
        assert active_entry is not None
        assert expired_waiter_entries[-1].ready_at > active_entry.ready_at

        _, execution_id = await create_task(
            owner,
            AnswererId.HUMAN_LITE,
            "再参加時のFIFOを検証するPrompt",
        )
        await human.match_available()

        active_state = await human.state(active_waiter.id)
        expired_state = await human.state(expired_waiter.id)
        assert active_state.assignment is not None
        assert active_state.assignment.execution_id == execution_id
        assert expired_state.status.value == "waiting"
    finally:
        await delete_users([item.id for item in users])


@pytest.mark.anyio
async def test_oldest_waiting_human_matches_once_and_skip_moves_to_next_human() -> None:
    owner = principal()
    first = principal()
    second = principal()
    users = [owner, first, second]
    factory = get_session_factory()
    human = HumanService(factory)

    async with factory() as session:
        session.add_all(
            UserModel(id=item.id, display_name=f"user-{index}") for index, item in enumerate(users)
        )
        await session.commit()

    try:
        assert (await human.ready(first.id)).status.value == "waiting"
        assert (await human.ready(second.id)).status.value == "waiting"
        async with factory() as session:
            waits = (
                await session.scalars(
                    select(HumanProfileModel).where(
                        HumanProfileModel.user_id.in_([first.id, second.id])
                    )
                )
            ).all()
            assert len(waits) == 2

        _, execution_id = await create_task(owner, AnswererId.HUMAN_LITE, "FIFOを検証するPrompt")
        await asyncio.gather(
            human.ready(first.id),
            human.match_available(),
            human.match_available(),
        )

        first_state = await human.state(first.id)
        second_state = await human.state(second.id)
        assert first_state.assignment is not None
        assert first_state.assignment.execution_id == execution_id
        assert second_state.status.value == "waiting"
        async with factory() as session:
            active_claims = await session.scalar(
                select(func.count())
                .select_from(HumanClaimModel)
                .where(HumanClaimModel.status == "active")
            )
        assert active_claims == 1

        await human.skip(first.id, first_state.assignment.claim_id)
        first_after_skip = await human.state(first.id)
        second_after_skip = await human.state(second.id)
        assert first_after_skip.status.value == "waiting"
        assert second_after_skip.assignment is not None
        assert second_after_skip.assignment.execution_id == execution_id
    finally:
        await delete_users([item.id for item in users])
