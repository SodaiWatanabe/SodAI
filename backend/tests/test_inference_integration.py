import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    GenerationJob,
)

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.domain.conversations import ConversationPrincipal, PrincipalKind
from app.domain.inference import InferenceEventDisposition
from app.domain.model_catalog import ModelId
from app.models.conversation import GuestSessionModel, InferenceOutboxModel
from app.repositories.conversations import SqlAlchemyConversationRepository
from app.services.inference.broker import RedisInferenceBroker

pytestmark = pytest.mark.skipif(
    os.getenv("SODAI_INTEGRATION_TESTS") != "1",
    reason="set SODAI_INTEGRATION_TESTS=1 to exercise local PostgreSQL and Redis",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_outbox_and_event_projection_round_trip_against_postgresql() -> None:
    principal = ConversationPrincipal(PrincipalKind.GUEST, uuid4())
    attempt_id = uuid4()
    deadline = datetime.now(timezone.utc) + timedelta(minutes=5)
    async with get_session_factory()() as session:
        session.add(
            GuestSessionModel(
                id=principal.id,
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=deadline,
                last_seen_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()
        repository = SqlAlchemyConversationRepository(session)
        assert await repository.reserve_inference_capacity(
            principal,
            ModelId.HINA,
            global_limit=10_000,
            guest_limit=100,
        )
        creation = await repository.create(
            principal,
            "統合テスト",
            ModelId.HINA,
            "hina@integration",
            attempt_id,
            deadline,
        )
        assert not await repository.reserve_inference_capacity(
            principal,
            ModelId.HINA,
            global_limit=10_000,
            guest_limit=1,
        )
        job = GenerationJob.create(
            run_id=creation.run.id,
            attempt_id=attempt_id,
            conversation_id=creation.conversation.id,
            model="hina",
            artifact_id="integration",
            turns=await repository.generation_turns(creation.conversation.id),
            deadline=deadline,
        )
        await repository.add_inference_outbox(creation.run.id, job.to_json())
        pending = await repository.pending_inference_outbox()
        assert job.to_json() in [item.payload for item in pending]
        outbox = next(item for item in pending if item.payload == job.to_json())
        await repository.mark_outbox_published(outbox.id)
        stored_outbox = await session.get(InferenceOutboxModel, outbox.id)
        assert stored_outbox is not None
        assert stored_outbox.payload == ""

        started = GenerationEvent.create(
            GenerationEventType.STARTED,
            run_id=creation.run.id,
            attempt_id=attempt_id,
            sequence=0,
            conversation_id=creation.conversation.id,
            resolved_model="hina@integration",
            input_tokens=4,
        )
        completed = GenerationEvent.create(
            GenerationEventType.COMPLETED,
            run_id=creation.run.id,
            attempt_id=attempt_id,
            sequence=1,
            conversation_id=creation.conversation.id,
            content="応答",
            output_tokens=2,
            finish_reason=FinishReason.STOP,
        )
        assert (await repository.project_inference_event(started)).disposition is (
            InferenceEventDisposition.APPLY
        )
        result = await repository.project_inference_event(completed)
        assert result.disposition is InferenceEventDisposition.APPLY
        assert result.projection is not None
        assert result.projection.content == "応答"
        await session.rollback()


@pytest.mark.anyio
async def test_event_acknowledgement_removes_redis_payload() -> None:
    settings = get_settings()
    suffix = uuid4().hex
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    broker = RedisInferenceBroker(
        redis,
        job_stream=f"test:jobs:{suffix}",
        event_stream=f"test:events:{suffix}",
        event_group=f"test:group:{suffix}",
        event_consumer="test-consumer",
        event_claim_idle_ms=1,
    )
    try:
        await broker.ensure_event_group()
        message_id = await redis.xadd(broker.event_stream, {"payload": "private conversation"})
        await redis.xreadgroup(
            groupname=broker.event_group,
            consumername="dead-consumer",
            streams={broker.event_stream: ">"},
            count=1,
        )

        await broker.acknowledge_event(message_id)

        assert await redis.xlen(broker.event_stream) == 0
        assert (await redis.xpending(broker.event_stream, broker.event_group))["pending"] == 0
    finally:
        await redis.delete(broker.event_stream)
        await broker.close()
