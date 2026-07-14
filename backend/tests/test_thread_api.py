from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.principal import get_principal
from app.domain.answerers import AnswererId
from app.domain.credits import InsufficientCreditsError
from app.domain.principals import Principal, PrincipalKind
from app.domain.responses import Execution, ResponseCreation, ResponseRequest, ResponseStatus
from app.domain.threads import Actor, ActorKind, Entry, EntryKind, Thread, ThreadSummary
from app.main import app
from app.repositories.threads import ThreadBusyError
from app.services.thread import ThreadService, get_thread_service

PRINCIPAL = Principal(
    PrincipalKind.GUEST,
    UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
)
SPACE_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
THREAD_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748c")
INPUT_ENTRY_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748d")
REQUEST_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748e")
EXECUTION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748f")
PARTNER_ACTOR_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb87490")
HINA_ACTOR_ID = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)


def creation_fixture() -> ResponseCreation:
    partner = Actor(PARTNER_ACTOR_ID, ActorKind.HUMAN, "guest:test", "対話相手")
    hina = Actor(HINA_ACTOR_ID, ActorKind.MODEL, "model:hina", "Hina")
    execution = Execution(
        id=EXECUTION_ID,
        response_request_id=REQUEST_ID,
        thread_id=THREAD_ID,
        result_entry_id=None,
        answerer=AnswererId.HINA,
        target="local:hina",
        status=ResponseStatus.QUEUED,
        attempt_no=1,
        attempt_id=UUID("018f96d4-7c48-7c27-a71f-591e3cb87491"),
        partial_output="",
        resolved_model=None,
        artifact_id="0123456789abcdef",
        error_code=None,
        created_at=NOW,
    )
    response = ResponseRequest(
        id=REQUEST_ID,
        thread_id=THREAD_ID,
        input_entry_id=INPUT_ENTRY_ID,
        requested_answerer=AnswererId.HINA,
        target_actor=hina,
        status=ResponseStatus.QUEUED,
        execution=execution,
        created_at=NOW,
    )
    thread = Thread(
        id=THREAD_ID,
        space_id=SPACE_ID,
        title="こんにちは",
        answerer=AnswererId.HINA,
        revision=1,
        entries=(
            Entry(
                id=INPUT_ENTRY_ID,
                thread_id=THREAD_ID,
                author=partner,
                kind=EntryKind.MESSAGE,
                content="こんにちは",
                ordinal=0,
                created_at=NOW,
            ),
        ),
        latest_response=response,
        created_at=NOW,
        updated_at=NOW,
        last_activity_at=NOW,
    )
    return ResponseCreation(thread=thread, response=response)


class StubThreadService:
    def __init__(self, *, busy: bool = False, insufficient: bool = False) -> None:
        self.busy = busy
        self.insufficient = insufficient
        self.received: tuple[Principal, str, AnswererId | None] | None = None

    async def create(
        self, principal: Principal, content: str, answerer: AnswererId | None
    ) -> ResponseCreation:
        if self.insufficient:
            raise InsufficientCreditsError
        self.received = (principal, content, answerer)
        return creation_fixture()

    async def append(
        self,
        principal: Principal,
        thread_id: UUID,
        content: str,
        answerer: AnswererId | None,
    ) -> ResponseCreation:
        if self.busy:
            raise ThreadBusyError
        self.received = (principal, content, answerer)
        assert thread_id == THREAD_ID
        return creation_fixture()

    async def retry(
        self,
        principal: Principal,
        response_request_id: UUID,
        idempotency_key: str,
    ) -> Execution:
        assert principal == PRINCIPAL
        assert response_request_id == REQUEST_ID
        assert idempotency_key == "retry-once"
        return creation_fixture().response.execution

    async def list(self, principal: Principal) -> list[ThreadSummary]:
        assert principal == PRINCIPAL
        thread = creation_fixture().thread
        return [
            ThreadSummary(
                id=thread.id,
                space_id=thread.space_id,
                title=thread.title,
                answerer=thread.answerer,
                revision=thread.revision,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                last_activity_at=thread.last_activity_at,
            )
        ]

    @staticmethod
    def available_answerers(principal: Principal):
        return ThreadService.available_answerers(principal)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_create_thread_exposes_actor_authorship_without_speaker_enum() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/threads", json={"input": "こんにちは", "answerer": "hina"}
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["thread"]["entries"][0]["author"]["kind"] == "human"
    assert "key" not in payload["thread"]["entries"][0]["author"]
    assert "speaker" not in payload["thread"]["entries"][0]
    assert payload["response"]["execution"]["status"] == "queued"
    assert service.received == (PRINCIPAL, "こんにちは", AnswererId.HINA)


@pytest.mark.anyio
async def test_response_request_is_a_first_class_endpoint() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/response-requests",
            json={"thread_id": str(THREAD_ID), "input": "続けて", "answerer": "hina"},
        )

    assert response.status_code == 202
    assert response.json()["response"]["requested_answerer"] == "hina"


@pytest.mark.anyio
async def test_response_request_rejects_blank_input_at_the_api_boundary() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/response-requests",
            json={"thread_id": str(THREAD_ID), "input": "   ", "answerer": "hina"},
        )

    assert response.status_code == 422
    assert service.received is None


@pytest.mark.anyio
async def test_response_execution_retry_requires_an_idempotency_key() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.post(
            f"/api/v1/response-requests/{REQUEST_ID}/executions"
        )
        retried = await client.post(
            f"/api/v1/response-requests/{REQUEST_ID}/executions",
            headers={"Idempotency-Key": " retry-once "},
        )

    assert missing.status_code == 422
    assert retried.status_code == 202
    assert retried.json()["id"] == str(EXECUTION_ID)
    assert retried.json()["attempt_no"] == 1


@pytest.mark.anyio
async def test_thread_rejects_concurrent_active_response() -> None:
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: StubThreadService(busy=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/response-requests",
            json={"thread_id": str(THREAD_ID), "input": "続けて", "answerer": "hina"},
        )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_thread_returns_payment_required_when_credits_are_exhausted() -> None:
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: StubThreadService(
        insufficient=True
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/threads", json={"input": "こんにちは", "answerer": "asuka-1"}
        )

    assert response.status_code == 402
    assert response.json() == {"detail": "Insufficient credits"}


@pytest.mark.anyio
async def test_old_conversation_endpoint_is_not_preserved() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/conversations")

    assert response.status_code == 404
