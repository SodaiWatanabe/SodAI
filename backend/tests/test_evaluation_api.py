from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.principal import get_principal
from app.domain.principals import Principal, PrincipalKind
from app.domain.responses import ResponseEvaluation, ResponseEvaluationValue
from app.main import app
from app.repositories.evaluations import (
    ResponseEvaluationNotFoundError,
    ResponseEvaluationNotReadyError,
)
from app.services.evaluations import get_response_evaluation_service

PRINCIPAL = Principal(
    PrincipalKind.GUEST,
    UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
)
EXECUTION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748f")
NOW = datetime(2026, 7, 31, 12, 34, tzinfo=timezone.utc)


class StubResponseEvaluationService:
    def __init__(self, *, missing: bool = False, not_ready: bool = False) -> None:
        self.missing = missing
        self.not_ready = not_ready
        self.set_received: tuple[
            Principal,
            UUID,
            ResponseEvaluationValue,
        ] | None = None
        self.clear_received: tuple[Principal, UUID] | None = None

    async def set(
        self,
        principal: Principal,
        execution_id: UUID,
        value: ResponseEvaluationValue,
    ) -> ResponseEvaluation:
        self._raise_if_unavailable()
        self.set_received = (principal, execution_id, value)
        return ResponseEvaluation(execution_id, value, NOW, NOW)

    async def clear(self, principal: Principal, execution_id: UUID) -> None:
        self._raise_if_unavailable()
        self.clear_received = (principal, execution_id)

    def _raise_if_unavailable(self) -> None:
        if self.missing:
            raise ResponseEvaluationNotFoundError
        if self.not_ready:
            raise ResponseEvaluationNotReadyError


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_evaluation_can_be_set_and_cleared() -> None:
    service = StubResponseEvaluationService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_response_evaluation_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        saved = await client.put(
            f"/api/v1/executions/{EXECUTION_ID}/evaluation",
            json={"value": "positive"},
        )
        cleared = await client.delete(
            f"/api/v1/executions/{EXECUTION_ID}/evaluation"
        )

    assert saved.status_code == 200
    assert saved.json() == {
        "execution_id": str(EXECUTION_ID),
        "value": "positive",
        "created_at": NOW.isoformat().replace("+00:00", "Z"),
        "updated_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    assert cleared.status_code == 204
    assert service.set_received == (
        PRINCIPAL,
        EXECUTION_ID,
        ResponseEvaluationValue.POSITIVE,
    )
    assert service.clear_received == (PRINCIPAL, EXECUTION_ID)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("service", "expected_status"),
    [
        (StubResponseEvaluationService(missing=True), 404),
        (StubResponseEvaluationService(not_ready=True), 409),
    ],
)
async def test_evaluation_hides_inaccessible_executions_and_requires_completion(
    service: StubResponseEvaluationService,
    expected_status: int,
) -> None:
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_response_evaluation_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.put(
            f"/api/v1/executions/{EXECUTION_ID}/evaluation",
            json={"value": "negative"},
        )

    assert response.status_code == expected_status


@pytest.mark.anyio
async def test_evaluation_rejects_unknown_values_at_the_api_boundary() -> None:
    service = StubResponseEvaluationService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_response_evaluation_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.put(
            f"/api/v1/executions/{EXECUTION_ID}/evaluation",
            json={"value": "five-stars"},
        )

    assert response.status_code == 422
    assert service.set_received is None
