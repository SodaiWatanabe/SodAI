import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    InferenceNamespace,
)
from sqlalchemy import delete, func, select
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId, get_answerer
from app.domain.execution_events import EventDisposition
from app.domain.principals import Principal, PrincipalKind
from app.domain.threads import ThreadSearchSource
from app.models.account import UserModel
from app.models.platform import (
    ActorModel,
    EntryTextContentModel,
    ExecutionModel,
    GuestSessionModel,
    OutboxEventModel,
    ResponseContextItemModel,
    ResponseRequestModel,
    ThreadEntryModel,
)
from app.repositories.threads import (
    ResponseNotRetryableError,
    ResponseRequestNotFoundError,
    SqlAlchemyThreadRepository,
    ThreadBusyError,
)
from app.services.inference.asuka import AsukaPseudoGenerator
from app.services.inference.billing import InferenceBillingService
from app.services.inference.broker import RedisInferenceBroker
from app.services.inference.coordinator import GenerationCoordinator
from app.services.inference.deployment import ModelDeploymentRegistry
from app.services.inference.pseudo_worker import PseudoGenerationWorker
from app.services.realtime import realtime_hub
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


@pytest.mark.anyio
async def test_generation_projection_creates_one_immutable_result_entry() -> None:
    principal = Principal(PrincipalKind.GUEST, uuid4())
    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    async with factory() as session:
        session.add(
            GuestSessionModel(
                id=principal.id,
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=now + timedelta(days=1),
                last_seen_at=now,
            )
        )
        await session.commit()

    try:
        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            context = await repository.ensure_personal_context(principal)
            creation = await repository.create_thread_response(
                principal,
                context,
                "こんにちは",
                get_answerer(AnswererId.HINA),
                execution_target="local:hina",
                artifact_id="integration",
                deadline_at=now + timedelta(minutes=5),
            )
            await repository.add_generation_outbox(
                creation.response.execution.id, '{"test":"terminal-discard"}'
            )
            await session.commit()
        execution = creation.response.execution
        async with factory() as session:
            mismatched = await SqlAlchemyThreadRepository(session).project_generation_event(
                GenerationEvent.create(
                    GenerationEventType.STARTED,
                    execution_id=execution.id,
                    attempt_id=execution.attempt_id,
                    sequence=0,
                    thread_id=uuid4(),
                    resolved_model="hina@integration",
                )
            )
            await session.commit()
        assert mismatched.disposition is EventDisposition.IGNORE

        events = (
            GenerationEvent.create(
                GenerationEventType.STARTED,
                execution_id=execution.id,
                attempt_id=execution.attempt_id,
                sequence=0,
                thread_id=creation.thread.id,
                resolved_model="hina@integration",
            ),
            GenerationEvent.create(
                GenerationEventType.DELTA,
                execution_id=execution.id,
                attempt_id=execution.attempt_id,
                sequence=1,
                thread_id=creation.thread.id,
                delta="こんに",
            ),
            GenerationEvent.create(
                GenerationEventType.COMPLETED,
                execution_id=execution.id,
                attempt_id=execution.attempt_id,
                sequence=2,
                thread_id=creation.thread.id,
                content="こんにちは。雛です。",
                finish_reason=FinishReason.STOP,
            ),
        )
        for event in events:
            async with factory() as session:
                result = await SqlAlchemyThreadRepository(session).project_generation_event(event)
                await session.commit()
                assert result.projection is not None

        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            assert await repository.discard_terminal_outbox() == 1
            outbox = await session.scalar(
                select(OutboxEventModel).where(OutboxEventModel.aggregate_id == execution.id)
            )
            await session.commit()
        assert outbox is not None
        assert outbox.discarded_at is not None
        assert outbox.published_at is None
        assert outbox.payload == ""

        async with factory() as session:
            thread = await SqlAlchemyThreadRepository(session).get(principal, creation.thread.id)

        assert [entry.content for entry in thread.entries] == [
            "こんにちは",
            "こんにちは。雛です。",
        ]
        assert thread.entries[-1].author.key == "model:hina"
        assert thread.latest_response is not None
        assert thread.latest_response.status.value == "completed"
        assert thread.latest_response.execution.result_entry_id == thread.entries[-1].id

        async with factory() as session:
            with pytest.raises(DBAPIError, match="entry text is immutable"):
                await session.execute(
                    delete(EntryTextContentModel).where(
                        EntryTextContentModel.entry_id == thread.entries[-1].id
                    )
                )
    finally:
        async with factory() as session:
            guest = await session.get(GuestSessionModel, principal.id)
            if guest is not None:
                await session.delete(guest)
                await session.commit()


@pytest.mark.anyio
async def test_thread_search_is_literal_scoped_and_excludes_archived_threads() -> None:
    owner = Principal(PrincipalKind.GUEST, uuid4())
    other = Principal(PrincipalKind.GUEST, uuid4())
    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    async with factory() as session:
        session.add_all(
            [
                GuestSessionModel(
                    id=principal.id,
                    token_hash=uuid4().hex + uuid4().hex,
                    expires_at=now + timedelta(days=1),
                    last_seen_at=now,
                )
                for principal in (owner, other)
            ]
        )
        await session.commit()

    try:
        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            owner_context = await repository.ensure_personal_context(owner)
            title_creation = await repository.create_thread_response(
                owner,
                owner_context,
                "元のタイトルには検索語がありません",
                get_answerer(AnswererId.HINA),
                execution_target="local:hina",
                artifact_id="integration",
                deadline_at=now + timedelta(minutes=5),
            )
            await repository.update_title(
                owner,
                title_creation.thread.id,
                "タイトルだけの検索語",
            )
            body_creation = await repository.create_thread_response(
                owner,
                owner_context,
                f"{'長い前置き' * 12}本文だけの検索語",
                get_answerer(AnswererId.HINA),
                execution_target="local:hina",
                artifact_id="integration",
                deadline_at=now + timedelta(minutes=5),
            )
            latest_body_entry = ThreadEntryModel(
                thread_id=body_creation.thread.id,
                author_actor_id=owner_context.actor.id,
                kind="message",
                ordinal=1,
            )
            latest_body_entry.text = EntryTextContentModel(
                content="本文だけの検索語をもう一度書きます",
            )
            session.add(latest_body_entry)
            percent_creation = await repository.create_thread_response(
                owner,
                owner_context,
                "記号は100%と_under\\scoreです",
                get_answerer(AnswererId.HINA),
                execution_target="local:hina",
                artifact_id="integration",
                deadline_at=now + timedelta(minutes=5),
            )
            other_context = await repository.ensure_personal_context(other)
            await repository.create_thread_response(
                other,
                other_context,
                "他人だけの秘密検索語",
                get_answerer(AnswererId.HINA),
                execution_target="local:hina",
                artifact_id="integration",
                deadline_at=now + timedelta(minutes=5),
            )
            await session.commit()

        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            title_page = await repository.search(owner, "タイトルだけ", limit=20)
            body_page = await repository.search(owner, "本文だけ", limit=20)
            percent_page = await repository.search(owner, "%", limit=20)
            underscore_page = await repository.search(owner, "_", limit=20)
            backslash_page = await repository.search(owner, "\\", limit=20)
            leaked_page = await repository.search(owner, "他人だけ", limit=20)
            limited_page = await repository.search(owner, "検索語", limit=1)

        assert len(title_page.items) == 1
        assert title_page.items[0].source is ThreadSearchSource.TITLE
        assert title_page.items[0].entry_id is None
        assert title_page.items[0].thread.id == title_creation.thread.id
        assert len(body_page.items) == 1
        assert body_page.items[0].source is ThreadSearchSource.ENTRY
        assert body_page.items[0].entry_id == latest_body_entry.id
        assert "本文だけの検索語" in body_page.items[0].snippet
        assert [hit.thread.id for hit in percent_page.items] == [percent_creation.thread.id]
        assert percent_page.items[0].source is ThreadSearchSource.ENTRY
        assert percent_page.items[0].entry_id == percent_creation.response.input_entry_id
        assert [hit.thread.id for hit in underscore_page.items] == [percent_creation.thread.id]
        assert [hit.thread.id for hit in backslash_page.items] == [percent_creation.thread.id]
        assert leaked_page.items == ()
        assert limited_page.has_more is True
        assert len(limited_page.items) == 1
        assert limited_page.items[0].thread.id == title_creation.thread.id

        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            await repository.archive(owner, percent_creation.thread.id)
            await session.commit()
        async with factory() as session:
            archived_page = await SqlAlchemyThreadRepository(session).search(
                owner,
                "%",
                limit=20,
            )
        assert archived_page.items == ()
    finally:
        async with factory() as session:
            guests = (
                await session.scalars(
                    select(GuestSessionModel).where(
                        GuestSessionModel.id.in_([owner.id, other.id])
                    )
                )
            ).all()
            for guest in guests:
                await session.delete(guest)
            await session.commit()


@pytest.mark.anyio
async def test_failed_response_retry_is_idempotent_and_preserves_context() -> None:
    settings = get_settings()
    factory = get_session_factory()
    principal = Principal(PrincipalKind.USER, uuid4())
    other_principal = Principal(PrincipalKind.USER, uuid4())
    service = ThreadService(factory, ModelDeploymentRegistry(settings.model_root), settings)

    async with factory() as session:
        session.add_all(
            [
                UserModel(id=principal.id, display_name="Retry owner"),
                UserModel(id=other_principal.id, display_name="Other owner"),
            ]
        )
        await session.commit()

    queue = None
    try:
        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            context = await repository.ensure_personal_context(principal)
            creation = await repository.create_thread_response(
                principal,
                context,
                "失敗した応答を再試行して",
                get_answerer(AnswererId.ASUKA_1),
                execution_target="pseudo:asuka-1",
                artifact_id="pseudo-v1",
                deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            await session.commit()

        first = creation.response.execution
        events = (
            GenerationEvent.create(
                GenerationEventType.STARTED,
                execution_id=first.id,
                attempt_id=first.attempt_id,
                sequence=0,
                thread_id=creation.thread.id,
                resolved_model="asuka-1@pseudo-v1",
            ),
            GenerationEvent.create(
                GenerationEventType.FAILED,
                execution_id=first.id,
                attempt_id=first.attempt_id,
                sequence=1,
                thread_id=creation.thread.id,
                error_code="test_failure",
            ),
        )
        for event in events:
            async with factory() as session:
                result = await SqlAlchemyThreadRepository(session).project_generation_event(event)
                await session.commit()
                assert result.disposition is EventDisposition.APPLY

        async with factory() as session:
            request = await session.get(ResponseRequestModel, creation.response.id)
            assert request is not None
            first_started_at = request.started_at
            with pytest.raises(ResponseRequestNotFoundError):
                await SqlAlchemyThreadRepository(session).retry_execution(
                    other_principal,
                    creation.response.id,
                    "0" * 64,
                    deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                    model_limit=32,
                    guest_model_limit=1,
                )

        queue, _ = realtime_hub.subscribe(principal, realtime_hub.cursor)
        second, replay = await asyncio.gather(
            service.retry(principal, creation.response.id, "retry-second"),
            service.retry(principal, creation.response.id, "retry-second"),
        )
        assert replay.id == second.id
        queued_event = await asyncio.wait_for(queue.get(), timeout=1)
        assert queued_event.type == "response.queued"
        assert queued_event.execution_id == second.id
        assert queued_event.data["attempt_no"] == 2

        with pytest.raises(ResponseNotRetryableError):
            await service.retry(principal, creation.response.id, "different-key")

        async with factory() as session:
            executions = (
                await session.scalars(
                    select(ExecutionModel)
                    .where(ExecutionModel.response_request_id == creation.response.id)
                    .order_by(ExecutionModel.attempt_no)
                )
            ).all()
            request = await session.get(ResponseRequestModel, creation.response.id)
            entry_count = await session.scalar(
                select(func.count())
                .select_from(ThreadEntryModel)
                .where(ThreadEntryModel.thread_id == creation.thread.id)
            )
            context_count = await session.scalar(
                select(func.count())
                .select_from(ResponseContextItemModel)
                .where(ResponseContextItemModel.response_request_id == creation.response.id)
            )
            outbox_count = await session.scalar(
                select(func.count())
                .select_from(OutboxEventModel)
                .where(OutboxEventModel.aggregate_id == second.id)
            )
        assert [execution.attempt_no for execution in executions] == [1, 2]
        assert executions[1].idempotency_key_hash not in {None, "retry-second"}
        assert request is not None
        assert request.started_at == first_started_at
        assert request.finished_at is None
        assert entry_count == 1
        assert context_count == 1
        assert outbox_count == 1

        async with factory() as session:
            delayed = await SqlAlchemyThreadRepository(session).project_generation_event(
                GenerationEvent.create(
                    GenerationEventType.DELTA,
                    execution_id=first.id,
                    attempt_id=first.attempt_id,
                    sequence=2,
                    thread_id=creation.thread.id,
                    delta="古い試行",
                )
            )
            await session.commit()
        assert delayed.disposition is EventDisposition.IGNORE

        async with factory() as session:
            result = await SqlAlchemyThreadRepository(session).project_generation_event(
                GenerationEvent.create(
                    GenerationEventType.FAILED,
                    execution_id=second.id,
                    attempt_id=second.attempt_id,
                    sequence=0,
                    thread_id=creation.thread.id,
                    error_code="second_failure",
                )
            )
            await InferenceBillingService(session).finalize(second.id)
            await session.commit()
        assert result.disposition is EventDisposition.APPLY

        third = await service.retry(principal, creation.response.id, "retry-third")
        assert third.attempt_no == 3
        thread = await service.get(principal, creation.thread.id)
        assert thread.latest_response is not None
        assert thread.latest_response.execution.id == third.id

        terminal_events = (
            GenerationEvent.create(
                GenerationEventType.STARTED,
                execution_id=third.id,
                attempt_id=third.attempt_id,
                sequence=0,
                thread_id=creation.thread.id,
                resolved_model="asuka-1@pseudo-v1",
            ),
            GenerationEvent.create(
                GenerationEventType.COMPLETED,
                execution_id=third.id,
                attempt_id=third.attempt_id,
                sequence=1,
                thread_id=creation.thread.id,
                content="再試行が完了しました。",
                finish_reason=FinishReason.STOP,
            ),
        )
        for event in terminal_events:
            async with factory() as session:
                result = await SqlAlchemyThreadRepository(session).project_generation_event(event)
                if event.type is GenerationEventType.COMPLETED:
                    await InferenceBillingService(session).finalize(third.id)
                await session.commit()
                assert result.disposition is EventDisposition.APPLY
        with pytest.raises(ResponseNotRetryableError):
            await service.retry(principal, creation.response.id, "after-completion")
        await service.archive(principal, creation.thread.id)
        with pytest.raises(ResponseRequestNotFoundError):
            await service.retry(principal, creation.response.id, "after-archive")
    finally:
        if queue is not None:
            realtime_hub.unsubscribe(principal, queue)
        async with factory() as session:
            actors = (
                await session.scalars(
                    select(ActorModel).where(
                        ActorModel.owner_user_id.in_([principal.id, other_principal.id])
                    )
                )
            ).all()
            for user_id in (principal.id, other_principal.id):
                user = await session.get(UserModel, user_id)
                if user is not None:
                    await session.delete(user)
            await session.flush()
            for actor in actors:
                await session.delete(actor)
            await session.commit()


@pytest.mark.anyio
async def test_append_and_retry_serialize_without_deadlock() -> None:
    settings = get_settings()
    factory = get_session_factory()
    principal = Principal(PrincipalKind.USER, uuid4())
    service = ThreadService(factory, ModelDeploymentRegistry(settings.model_root), settings)

    async with factory() as session:
        session.add(UserModel(id=principal.id, display_name="Concurrency owner"))
        await session.commit()

    try:
        async with factory() as session:
            repository = SqlAlchemyThreadRepository(session)
            context = await repository.ensure_personal_context(principal)
            creation = await repository.create_thread_response(
                principal,
                context,
                "競合を検証して",
                get_answerer(AnswererId.ASUKA_1),
                execution_target="pseudo:asuka-1",
                artifact_id="pseudo-v1",
                deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            await session.commit()
        execution = creation.response.execution
        async with factory() as session:
            await SqlAlchemyThreadRepository(session).project_generation_event(
                GenerationEvent.create(
                    GenerationEventType.FAILED,
                    execution_id=execution.id,
                    attempt_id=execution.attempt_id,
                    sequence=0,
                    thread_id=creation.thread.id,
                    error_code="test_failure",
                )
            )
            await session.commit()

        results = await asyncio.wait_for(
            asyncio.gather(
                service.retry(principal, creation.response.id, "concurrent-retry"),
                service.append(
                    principal,
                    creation.thread.id,
                    "新しい入力",
                    AnswererId.ASUKA_1,
                ),
                return_exceptions=True,
            ),
            timeout=3,
        )
        successes = [result for result in results if not isinstance(result, Exception)]
        failures = [result for result in results if isinstance(result, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], (ResponseNotRetryableError, ThreadBusyError))
        success = successes[0]
        active_execution = (
            success.response.execution if hasattr(success, "response") else success
        )
        async with factory() as session:
            await SqlAlchemyThreadRepository(session).project_generation_event(
                GenerationEvent.create(
                    GenerationEventType.FAILED,
                    execution_id=active_execution.id,
                    attempt_id=active_execution.attempt_id,
                    sequence=0,
                    thread_id=creation.thread.id,
                    error_code="test_cleanup",
                )
            )
            await InferenceBillingService(session).finalize(active_execution.id)
            await session.commit()
    finally:
        async with factory() as session:
            actor = await session.scalar(
                select(ActorModel).where(ActorModel.owner_user_id == principal.id)
            )
            user = await session.get(UserModel, principal.id)
            if user is not None:
                await session.delete(user)
                await session.flush()
            if actor is not None:
                await session.delete(actor)
            await session.commit()


@pytest.mark.anyio
async def test_asuka_completes_through_the_shared_generation_pipeline() -> None:
    settings = get_settings()
    factory = get_session_factory()
    principal = Principal(PrincipalKind.USER, uuid4())
    namespace = InferenceNamespace(f"sodai:test:{uuid4().hex}:inference")
    broker_redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    worker_redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    cleanup_redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    coordinator = GenerationCoordinator(
        factory,
        RedisInferenceBroker(
            broker_redis,
            namespace=namespace,
            event_consumer="integration-projector",
            event_claim_idle_ms=500,
        ),
        reconciliation_interval_seconds=0.1,
    )
    worker = PseudoGenerationWorker(
        worker_redis,
        AsukaPseudoGenerator(),
        namespace=namespace,
        consumer_name="integration-asuka",
    )
    service = ThreadService(factory, ModelDeploymentRegistry(settings.model_root), settings)
    execution_attempt_id = None

    async with factory() as session:
        session.add(UserModel(id=principal.id, display_name="Asuka integration"))
        await session.commit()

    coordinator.start()
    worker.start()
    try:
        creation = await service.create(principal, "こんにちは", AnswererId.ASUKA_1)
        execution_attempt_id = creation.response.execution.attempt_id

        deadline = asyncio.get_running_loop().time() + 12
        while True:
            thread = await service.get(principal, creation.thread.id)
            if thread.latest_response is not None and thread.latest_response.status.value in {
                "completed",
                "failed",
            }:
                break
            if asyncio.get_running_loop().time() >= deadline:
                pytest.fail("Asuka generation did not reach a terminal state")
            await asyncio.sleep(0.05)

        assert thread.latest_response is not None
        assert thread.latest_response.status.value == "completed"
        assert thread.latest_response.execution.result_entry_id == thread.entries[-1].id
        assert thread.entries[-1].author.key == "model:asuka-1"
        assert len(thread.entries[-1].content) > 80
    finally:
        await worker.stop()
        await coordinator.stop()
        keys = [
            namespace.event_stream,
            namespace.job_stream_for("asuka-1", worker.artifact_id),
        ]
        if execution_attempt_id is not None:
            keys.append(namespace.attempt_lock(execution_attempt_id))
            keys.append(namespace.attempt_progress(execution_attempt_id))
        await cleanup_redis.delete(*keys)
        await cleanup_redis.aclose()
        async with factory() as session:
            user = await session.get(UserModel, principal.id)
            actor = await session.scalar(
                select(ActorModel).where(ActorModel.owner_user_id == principal.id)
            )
            if user is not None:
                await session.delete(user)
                await session.flush()
            if actor is not None:
                await session.delete(actor)
            await session.commit()
