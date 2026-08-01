from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.inference_operations import (
    DatabaseInferenceSnapshot,
    InferenceOperationsSnapshot,
    OperationalStatus,
    StreamGroupSnapshot,
)
from app.main import app
from app.services.inference.operations import get_inference_operations_service
from app.services.readiness import get_readiness_service


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "SodAI API",
        "environment": "development",
    }


@pytest.mark.anyio
async def test_readiness() -> None:
    class StubReadinessService:
        @staticmethod
        async def check() -> None:
            return None

    app.dependency_overrides[get_readiness_service] = StubReadinessService
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.anyio
async def test_readiness_hides_dependency_failure() -> None:
    class StubReadinessService:
        @staticmethod
        async def check() -> None:
            raise ConnectionError("private dependency details")

    app.dependency_overrides[get_readiness_service] = StubReadinessService
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "private dependency details" not in response.text


@pytest.mark.anyio
async def test_inference_health_exposes_only_the_coarse_status() -> None:
    class StubOperationsService:
        @staticmethod
        async def snapshot():
            return InferenceOperationsSnapshot(
                status=OperationalStatus.DEGRADED,
                checked_at=datetime.now(timezone.utc),
                database=DatabaseInferenceSnapshot(
                    available=True,
                    schema_revision="secret-revision",
                    queued=3,
                    running=1,
                    failed_last_hour=2,
                    pending_outbox=1,
                    oldest_pending_outbox_at=None,
                    oldest_queued_at=None,
                    active_by_answerer={},
                    active_artifacts={},
                ),
                redis_available=True,
                event_stream=StreamGroupSnapshot(
                    pending=4,
                    lag=5,
                    oldest_pending_idle_ms=100,
                    oldest_backlog_age_ms=100,
                ),
                runtimes=(),
            )

    app.dependency_overrides[get_inference_operations_service] = StubOperationsService
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health/inference")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "degraded"}
