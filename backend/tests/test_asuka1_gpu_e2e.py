import asyncio
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sodai_contracts.inference import InferenceNamespace
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import selectinload

from app.auth.principal import get_principal
from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.domain.credits import CREDIT_SCALE, CreditSourceKind
from app.domain.principals import Principal, PrincipalKind
from app.main import app
from app.models.account import UserModel
from app.models.credits import InferenceUsageRecordModel
from app.models.platform import ExecutionModel
from app.repositories.credits import CreditLedgerRepository
from app.services.inference.broker import RedisInferenceBroker
from app.services.inference.coordinator import GenerationCoordinator
from app.services.inference.deployment import ModelDeploymentRegistry
from app.services.realtime import RealtimeEvent, realtime_hub
from app.services.thread import ThreadService, get_thread_service

pytestmark = pytest.mark.skipif(
    os.getenv("SODAI_GPU_E2E") != "1",
    reason="run through make test-asuka1-e2e",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_asuka1_completes_through_api_stream_and_projection() -> None:
    settings = get_settings()
    database_name = make_url(settings.database_url).database or ""
    assert database_name.startswith("sodai_e2e_")
    assert settings.inference_namespace.startswith("sodai:e2e:")
    model = os.environ["SODAI_GPU_E2E_MODEL"]
    assert model == "asuka-1.1"
    assert os.environ["SODAI_E2E_DEVICE_USED"].startswith("cuda")
    namespace = InferenceNamespace(settings.inference_namespace)

    factory = get_session_factory()
    principal = Principal(PrincipalKind.USER, uuid4())
    async with factory() as session:
        session.add(UserModel(id=principal.id, display_name=f"{model} E2E"))
        await session.flush()
        await CreditLedgerRepository(session).grant(
            principal.id,
            CREDIT_SCALE,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key=f"{model}-e2e-{principal.id}",
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
        cancellation_ttl_seconds=settings.inference_job_timeout_seconds + 60,
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
                json={"input": "こんにちは", "answerer": model},
            )
            assert created_response.status_code == 201, created_response.text
            creation = created_response.json()
            thread_id = creation["thread"]["id"]
            execution_id = creation["response"]["execution"]["id"]

            event_types: list[str] = []
            public_events: list[RealtimeEvent] = []
            deadline = asyncio.get_running_loop().time() + 180
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    if str(event.thread_id) == thread_id:
                        event_types.append(event.type)
                        public_events.append(event)
                except asyncio.TimeoutError:
                    pass
                response = await client.get(f"/api/v1/threads/{thread_id}")
                assert response.status_code == 200
                thread = response.json()
                status = thread["latest_response"]["status"]
                if status in {"completed", "failed"}:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    pytest.fail("Asuka 1.1 generation did not reach a terminal state")

        assert status == "completed", thread["latest_response"]["execution"]["error_code"]
        assert len(thread["entries"]) == 2
        assert thread["entries"][-1]["content"].strip()
        assert "response.started" in event_types
        assert "response.phase" in event_types
        assert "response.delta" in event_types
        assert "response.completed" in event_types
        assert event_types.index("response.phase") < event_types.index("response.delta")
        started = next(event for event in public_events if event.type == "response.started")
        phase = next(event for event in public_events if event.type == "response.phase")
        assert started.data["phase"] == "thinking"
        assert phase.data["phase"] == "answering"
        for event in public_events:
            assert {
                "thinking_content",
                "thinking_output",
                "thinking_tokens",
                "answer_tokens",
            }.isdisjoint(event.data)

        public_execution = thread["latest_response"]["execution"]
        assert public_execution["generation_phase"] is None
        assert "thinking_output" not in public_execution
        assert "thinking_tokens" not in public_execution
        assert "answer_tokens" not in public_execution

        async with factory() as session:
            execution = await session.scalar(
                select(ExecutionModel)
                .where(ExecutionModel.id == execution_id)
                .options(selectinload(ExecutionModel.model_execution))
            )
            usage = await session.get(InferenceUsageRecordModel, execution_id)
            assert execution is not None
            assert execution.status == "completed"
            assert execution.model_execution.resolved_model.startswith("asuka-1@")
            assert (execution.input_tokens or 0) > 0
            assert (execution.output_tokens or 0) > 0
            assert execution.thinking_output is not None
            assert execution.thinking_tokens is not None
            assert execution.answer_tokens is not None
            assert execution.output_tokens is not None
            assert execution.thinking_tokens >= 0
            assert execution.answer_tokens > 0
            assert (
                execution.output_tokens
                >= execution.thinking_tokens + execution.answer_tokens
            )
            assert execution.generation_phase is None
            assert usage is not None
            assert usage.charged_amount == CREDIT_SCALE // 10
    finally:
        app.dependency_overrides.clear()
        realtime_hub.unsubscribe(principal, queue)
        await coordinator.stop()
        await dispose_engine()
