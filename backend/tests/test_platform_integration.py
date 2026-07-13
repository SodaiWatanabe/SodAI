import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sodai_contracts.inference import FinishReason, GenerationEvent, GenerationEventType
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId, get_answerer
from app.domain.execution_events import EventDisposition
from app.domain.principals import Principal, PrincipalKind
from app.models.account import UserModel
from app.models.platform import (
    ActorModel,
    EntryTextContentModel,
    GuestSessionModel,
    OutboxEventModel,
)
from app.repositories.threads import SqlAlchemyThreadRepository
from app.services.inference.asuka import AsukaPseudoGenerator
from app.services.inference.broker import RedisInferenceBroker
from app.services.inference.coordinator import GenerationCoordinator
from app.services.inference.deployment import ModelDeploymentRegistry
from app.services.inference.pseudo_worker import PseudoGenerationWorker
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
async def test_asuka_completes_through_the_shared_generation_pipeline() -> None:
    settings = get_settings()
    factory = get_session_factory()
    principal = Principal(PrincipalKind.USER, uuid4())
    namespace = f"sodai:test:{uuid4().hex}"
    job_stream = f"{namespace}:jobs"
    event_stream = f"{namespace}:events"
    event_group = f"{namespace}:projector"
    worker_group = f"{namespace}:workers"
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
            job_stream=job_stream,
            event_stream=event_stream,
            event_group=event_group,
            event_consumer="integration-projector",
            event_claim_idle_ms=500,
        ),
        reconciliation_interval_seconds=0.1,
    )
    worker = PseudoGenerationWorker(
        worker_redis,
        AsukaPseudoGenerator(),
        job_stream=job_stream,
        event_stream=event_stream,
        worker_group=worker_group,
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
        keys = [event_stream, f"{job_stream}:asuka-1:{worker.artifact_id}"]
        if execution_attempt_id is not None:
            keys.append(f"sodai:inference:attempt:{execution_attempt_id}")
            keys.append(f"sodai:inference:attempt:{execution_attempt_id}:progress")
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
