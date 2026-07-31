from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.principal import get_principal
from app.domain.answerers import AnswererId
from app.domain.credits import InsufficientCreditsError
from app.domain.principals import Principal, PrincipalKind
from app.domain.reasoning import ReasoningEffort
from app.domain.responses import (
    Execution,
    ResponseCreation,
    ResponseEvaluationValue,
    ResponseRequest,
    ResponseStatus,
)
from app.domain.threads import (
    Actor,
    ActorKind,
    Entry,
    EntryKind,
    Thread,
    ThreadSearchHit,
    ThreadSearchPage,
    ThreadSearchSource,
    ThreadSummary,
)
from app.main import app
from app.repositories.threads import ExecutionNotFoundError, ThreadBusyError
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
RESULT_ENTRY_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb87492")
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


def completed_thread_fixture() -> Thread:
    creation = creation_fixture()
    execution = replace(
        creation.response.execution,
        result_entry_id=RESULT_ENTRY_ID,
        status=ResponseStatus.COMPLETED,
        partial_output="回答です。",
        resolved_model="hina@api-test",
        evaluation=ResponseEvaluationValue.POSITIVE,
    )
    response = replace(
        creation.response,
        status=ResponseStatus.COMPLETED,
        execution=execution,
    )
    result_entry = Entry(
        id=RESULT_ENTRY_ID,
        thread_id=THREAD_ID,
        author=response.target_actor,
        kind=EntryKind.MESSAGE,
        content="回答です。",
        ordinal=1,
        created_at=NOW,
        answerer=AnswererId.HINA,
        response_status=ResponseStatus.COMPLETED,
        execution_id=EXECUTION_ID,
        evaluation=ResponseEvaluationValue.POSITIVE,
    )
    return replace(
        creation.thread,
        entries=(*creation.thread.entries, result_entry),
        latest_response=response,
    )


def cancelled_thread_fixture() -> Thread:
    completed = completed_thread_fixture()
    result_entry = replace(
        completed.entries[-1],
        content="回答の途中",
        response_status=ResponseStatus.CANCELLED,
        evaluation=None,
    )
    response = replace(
        completed.latest_response,
        status=ResponseStatus.CANCELLED,
        execution=replace(
            completed.latest_response.execution,
            status=ResponseStatus.CANCELLED,
            partial_output="回答の途中",
            evaluation=None,
        ),
    )
    return replace(
        completed,
        entries=(*completed.entries[:-1], result_entry),
        latest_response=response,
    )


class StubThreadService:
    def __init__(
        self,
        *,
        busy: bool = False,
        insufficient: bool = False,
        missing_execution: bool = False,
    ) -> None:
        self.busy = busy
        self.insufficient = insufficient
        self.missing_execution = missing_execution
        self.received: (
            tuple[Principal, str, AnswererId | None, ReasoningEffort | None] | None
        ) = None
        self.search_received: tuple[Principal, str, int] | None = None
        self.cancel_received: tuple[Principal, UUID] | None = None

    async def create(
        self,
        principal: Principal,
        content: str,
        answerer: AnswererId | None,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> ResponseCreation:
        if self.insufficient:
            raise InsufficientCreditsError
        self.received = (principal, content, answerer, reasoning_effort)
        return creation_fixture()

    async def append(
        self,
        principal: Principal,
        thread_id: UUID,
        content: str,
        answerer: AnswererId | None,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> ResponseCreation:
        if self.busy:
            raise ThreadBusyError
        self.received = (principal, content, answerer, reasoning_effort)
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

    async def cancel(self, principal: Principal, execution_id: UUID) -> Thread:
        if self.missing_execution:
            raise ExecutionNotFoundError
        self.cancel_received = (principal, execution_id)
        return cancelled_thread_fixture()

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

    async def get(self, principal: Principal, thread_id: UUID) -> Thread:
        assert principal == PRINCIPAL
        assert thread_id == THREAD_ID
        return completed_thread_fixture()

    async def search(
        self,
        principal: Principal,
        query: str,
        *,
        limit: int,
    ) -> ThreadSearchPage:
        self.search_received = (principal, query, limit)
        thread = creation_fixture().thread
        summary = ThreadSummary(
            id=thread.id,
            space_id=thread.space_id,
            title=thread.title,
            answerer=thread.answerer,
            revision=thread.revision,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            last_activity_at=thread.last_activity_at,
        )
        return ThreadSearchPage(
            items=(
                ThreadSearchHit(
                    thread=summary,
                    source=ThreadSearchSource.ENTRY,
                    entry_id=INPUT_ENTRY_ID,
                    snippet="こんにちは",
                ),
            ),
            has_more=False,
        )

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
    assert payload["thread"]["entries"][0]["answerer"] is None
    assert "resolved_model" not in payload["thread"]["entries"][0]
    assert "key" not in payload["thread"]["entries"][0]["author"]
    assert "speaker" not in payload["thread"]["entries"][0]
    assert payload["response"]["execution"]["status"] == "queued"
    assert service.received == (PRINCIPAL, "こんにちは", AnswererId.HINA, None)


@pytest.mark.anyio
async def test_read_thread_exposes_result_answerer_without_internal_model() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/threads/{THREAD_ID}")

    assert response.status_code == 200
    result_entry = response.json()["entries"][-1]
    assert result_entry["answerer"] == "hina"
    assert result_entry["execution_id"] == str(EXECUTION_ID)
    assert result_entry["evaluation"] == "positive"
    assert response.json()["latest_response"]["execution"]["evaluation"] == "positive"
    assert "resolved_model" not in result_entry


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
async def test_response_request_accepts_shared_reasoning_effort() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/response-requests",
            json={
                "thread_id": str(THREAD_ID),
                "input": "深く考えて",
                "answerer": "hina",
                "reasoning_effort": "xhigh",
            },
        )

    assert response.status_code == 202
    assert service.received == (
        PRINCIPAL,
        "深く考えて",
        AnswererId.HINA,
        ReasoningEffort.XHIGH,
    )


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
async def test_thread_search_returns_message_context_without_exposing_actor_keys() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/thread-searches",
            json={"query": "  こんにちは  ", "limit": 12},
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "thread": {
                    "id": str(THREAD_ID),
                    "space_id": str(SPACE_ID),
                    "title": "こんにちは",
                    "answerer": "hina",
                    "revision": 1,
                    "created_at": NOW.isoformat().replace("+00:00", "Z"),
                    "updated_at": NOW.isoformat().replace("+00:00", "Z"),
                    "last_activity_at": NOW.isoformat().replace("+00:00", "Z"),
                },
                "source": "entry",
                "entry_id": str(INPUT_ENTRY_ID),
                "snippet": "こんにちは",
            }
        ],
        "has_more": False,
    }
    assert service.search_received == (PRINCIPAL, "こんにちは", 12)


@pytest.mark.anyio
async def test_thread_search_rejects_blank_query_at_the_api_boundary() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/thread-searches",
            json={"query": "   "},
        )

    assert response.status_code == 422
    assert service.search_received is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"query": "長" * 101},
        {"query": "検索", "limit": 0},
        {"query": "検索", "limit": 51},
    ],
)
async def test_thread_search_rejects_oversized_requests(payload: dict[str, object]) -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/thread-searches", json=payload)

    assert response.status_code == 422
    assert service.search_received is None


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
async def test_response_execution_can_be_cancelled_idempotently() -> None:
    service = StubThreadService()
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/executions/{EXECUTION_ID}/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_response"]["status"] == "cancelled"
    assert payload["entries"][-1]["content"] == "回答の途中"
    assert payload["entries"][-1]["response_status"] == "cancelled"
    assert service.cancel_received == (PRINCIPAL, EXECUTION_ID)


@pytest.mark.anyio
async def test_response_execution_cancellation_hides_inaccessible_executions() -> None:
    app.dependency_overrides[get_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_thread_service] = lambda: StubThreadService(
        missing_execution=True
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/executions/{EXECUTION_ID}/cancel")

    assert response.status_code == 404


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
