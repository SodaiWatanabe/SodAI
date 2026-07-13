import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sodai_contracts.inference import (
    FinishReason,
    GenerationEvent,
    GenerationEventType,
    InferenceNamespace,
)
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import selectinload

from app.auth.principal import get_principal
from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.domain.execution_events import EventDisposition
from app.domain.principals import Principal, PrincipalKind
from app.main import app
from app.models.credits import InferenceUsageRecordModel
from app.models.platform import (
    ExecutionModel,
    GuestSessionModel,
    OutboxEventModel,
    ThreadEntryModel,
)
from app.repositories.threads import SqlAlchemyThreadRepository
from app.services.inference.broker import RedisInferenceBroker
from app.services.inference.coordinator import GenerationCoordinator
from app.services.inference.deployment import ModelDeploymentRegistry
from app.services.realtime import realtime_hub
from app.services.thread import ThreadService, get_thread_service

pytestmark = pytest.mark.skipif(
    os.getenv("SODAI_GPU_E2E") != "1",
    reason="run through infra/scripts/test-inference-e2e.sh",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_hina_completes_through_api_stream_and_projection() -> None:
    settings = get_settings()
    database_name = make_url(settings.database_url).database or ""
    assert database_name.startswith("sodai_e2e_")
    assert settings.inference_namespace.startswith("sodai:e2e:")
    assert os.environ["HINA_E2E_DEVICE_USED"].startswith("cuda")
    namespace = InferenceNamespace(settings.inference_namespace)

    factory = get_session_factory()
    principal = Principal(PrincipalKind.GUEST, uuid4())
    now = datetime.now(timezone.utc)
    async with factory() as session:
        session.add(
            GuestSessionModel(
                id=principal.id,
                token_hash=uuid4().hex + uuid4().hex,
                expires_at=now + timedelta(hours=1),
                last_seen_at=now,
            )
        )
        await session.commit()

    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    coordinator = GenerationCoordinator(
        factory,
        RedisInferenceBroker(
            redis,
            namespace=namespace,
            event_consumer=f"e2e-projector-{uuid4().hex}",
            event_claim_idle_ms=500,
        ),
        reconciliation_interval_seconds=0.1,
    )
    service = ThreadService(factory, ModelDeploymentRegistry(settings.model_root), settings)
    queue, _ = realtime_hub.subscribe(principal, realtime_hub.cursor)
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_thread_service] = lambda: service
    coordinator.start()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created_response = await client.post(
                "/api/v1/threads",
                json={"input": "こんにちは。短く自己紹介してください。", "answerer": "hina"},
            )
            assert created_response.status_code == 201
            creation = created_response.json()
            thread_id = creation["thread"]["id"]
            execution_id = creation["response"]["execution"]["id"]

            event_types: list[str] = []
            deadline = asyncio.get_running_loop().time() + 180
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    if str(event.thread_id) == thread_id:
                        event_types.append(event.type)
                except asyncio.TimeoutError:
                    pass
                response = await client.get(f"/api/v1/threads/{thread_id}")
                assert response.status_code == 200
                thread = response.json()
                status = thread["latest_response"]["status"]
                if status in {"completed", "failed"}:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    pytest.fail("Hina generation did not reach a terminal state")

        assert status == "completed", thread["latest_response"]["execution"]["error_code"]
        assert len(thread["entries"]) == 2
        assert thread["entries"][-1]["content"].strip()
        assert "response.started" in event_types
        assert "response.delta" in event_types
        assert "response.completed" in event_types

        async with factory() as session:
            execution = await session.scalar(
                select(ExecutionModel)
                .where(ExecutionModel.id == execution_id)
                .options(selectinload(ExecutionModel.model_execution))
            )
            outbox = await session.scalar(
                select(OutboxEventModel).where(
                    OutboxEventModel.aggregate_id == execution_id
                )
            )
            usage = await session.get(InferenceUsageRecordModel, execution_id)
            assert execution is not None
            assert execution.status == "completed"
            assert (execution.input_tokens or 0) > 0
            assert (execution.output_tokens or 0) > 0
            assert execution.model_execution.resolved_model
            assert outbox is not None
            assert outbox.published_at is not None
            assert outbox.payload == ""
            assert execution.last_event_id is not None
            assert execution.last_event_type is not None
            assert execution.finish_reason is not None
            assert usage is not None
            assert usage.input_tokens == execution.input_tokens
            assert usage.output_tokens == execution.output_tokens
            assert usage.charged_amount == 0
            assert usage.billing_reason == "free"

            replay = GenerationEvent(
                id=execution.last_event_id,
                type=GenerationEventType(execution.last_event_type),
                execution_id=execution.id,
                attempt_id=execution.attempt_id,
                sequence=execution.last_event_sequence,
                thread_id=execution.thread_id,
                occurred_at=datetime.now(timezone.utc),
                content=execution.partial_output,
                output_tokens=execution.output_tokens,
                finish_reason=FinishReason(execution.finish_reason),
            )
            replayed = await SqlAlchemyThreadRepository(
                session
            ).project_generation_event(replay)
            await session.commit()
            entry_count = await session.scalar(
                select(func.count())
                .select_from(ThreadEntryModel)
                .where(ThreadEntryModel.thread_id == execution.thread_id)
            )
        assert replayed.disposition is EventDisposition.REPLAY
        assert entry_count == 2
    finally:
        app.dependency_overrides.clear()
        realtime_hub.unsubscribe(principal, queue)
        await coordinator.stop()
        async with factory() as session:
            guest = await session.get(GuestSessionModel, principal.id)
            if guest is not None:
                await session.delete(guest)
                await session.commit()
        await dispose_engine()
