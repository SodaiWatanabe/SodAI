from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.principal import get_conversation_principal
from app.domain.conversations import (
    Conversation,
    ConversationCreation,
    ConversationPrincipal,
    ConversationSummary,
    InferenceRun,
    Message,
    MessageStatus,
    PrincipalKind,
    RunStatus,
    Speaker,
)
from app.domain.model_catalog import ModelId
from app.main import app
from app.repositories.conversations import ConversationBusyError
from app.services.conversation import (
    ConversationService,
    InferenceCapacityError,
    get_conversation_service,
)

PRINCIPAL = ConversationPrincipal(
    PrincipalKind.GUEST,
    UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
)
CONVERSATION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
INPUT_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748c")
OUTPUT_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748d")
RUN_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748e")
ATTEMPT_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748f")
NOW = datetime(2026, 7, 12, 13, 0, tzinfo=timezone.utc)


def creation_fixture() -> ConversationCreation:
    messages = (
        Message(
            id=INPUT_ID,
            conversation_id=CONVERSATION_ID,
            speaker=Speaker.PARTNER,
            content="こんにちは",
            status=MessageStatus.COMPLETED,
            ordinal=0,
            created_at=NOW,
            updated_at=NOW,
        ),
        Message(
            id=OUTPUT_ID,
            conversation_id=CONVERSATION_ID,
            speaker=Speaker.SODAI,
            content="",
            status=MessageStatus.STREAMING,
            ordinal=1,
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    run = InferenceRun(
        id=RUN_ID,
        conversation_id=CONVERSATION_ID,
        input_message_id=INPUT_ID,
        output_message_id=OUTPUT_ID,
        attempt_id=ATTEMPT_ID,
        requested_model=ModelId.HINA,
        resolved_model="hina@artifact",
        status=RunStatus.QUEUED,
        created_at=NOW,
    )
    return ConversationCreation(
        conversation=Conversation(
            id=CONVERSATION_ID,
            title="こんにちは",
            model=ModelId.HINA,
            messages=messages,
            active_run=run,
            created_at=NOW,
            updated_at=NOW,
            last_activity_at=NOW,
        ),
        run=run,
    )


class StubConversationService:
    def __init__(self, *, busy: bool = False, capacity_exhausted: bool = False) -> None:
        self.busy = busy
        self.capacity_exhausted = capacity_exhausted
        self.received: tuple[ConversationPrincipal, str, ModelId] | None = None

    async def create(
        self, principal: ConversationPrincipal, content: str, model: ModelId | None
    ) -> ConversationCreation:
        if self.capacity_exhausted:
            raise InferenceCapacityError
        selected = ConversationService.select_model(principal, model)
        self.received = (principal, content, selected.id)
        return creation_fixture()

    async def add_turn(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        content: str,
        model: ModelId | None,
    ) -> ConversationCreation:
        if self.capacity_exhausted:
            raise InferenceCapacityError
        if self.busy:
            raise ConversationBusyError
        selected = ConversationService.select_model(principal, model)
        self.received = (principal, content, selected.id)
        return creation_fixture()

    async def update_title(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        title: str,
    ) -> ConversationSummary:
        self.received = (principal, title, ModelId.HINA)
        conversation = creation_fixture().conversation
        return ConversationSummary(
            id=conversation_id,
            title=title.strip(),
            model=conversation.model,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_activity_at=conversation.last_activity_at,
        )

    async def archive(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
    ) -> None:
        self.received = (principal, str(conversation_id), ModelId.HINA)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_create_conversation_uses_sodai_partner_vocabulary() -> None:
    service = StubConversationService()
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/conversations",
            json={"input": "こんにちは", "model": "hina"},
        )

    assert response.status_code == 201
    assert [message["speaker"] for message in response.json()["conversation"]["messages"]] == [
        "partner",
        "sodai",
    ]
    assert response.json()["run"]["resolved_model"] == "hina@artifact"
    assert service.received == (PRINCIPAL, "こんにちは", ModelId.HINA)


@pytest.mark.anyio
async def test_create_conversation_defaults_to_hina() -> None:
    service = StubConversationService()
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/conversations",
            json={"input": "こんにちは"},
        )

    assert response.status_code == 201
    assert service.received == (PRINCIPAL, "こんにちは", ModelId.HINA)


@pytest.mark.anyio
async def test_create_turn_reports_active_generation_conflict() -> None:
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: StubConversationService(busy=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/conversations/{CONVERSATION_ID}/turns",
            json={"input": "続けましょう", "model": "hina"},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "A response is already being generated"}


@pytest.mark.anyio
async def test_create_conversation_rejects_work_beyond_inference_capacity() -> None:
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: StubConversationService(
        capacity_exhausted=True
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/conversations",
            json={"input": "こんにちは", "model": "hina"},
        )

    assert response.status_code == 429
    assert response.json() == {"detail": "Inference capacity is exhausted"}


@pytest.mark.anyio
async def test_update_conversation_title() -> None:
    service = StubConversationService()
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/conversations/{CONVERSATION_ID}",
            json={"title": "  新しい名前  "},
        )

    assert response.status_code == 200
    assert response.json()["title"] == "新しい名前"
    assert service.received == (PRINCIPAL, "新しい名前", ModelId.HINA)


@pytest.mark.anyio
async def test_update_conversation_rejects_blank_title() -> None:
    service = StubConversationService()
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/conversations/{CONVERSATION_ID}",
            json={"title": "   "},
        )

    assert response.status_code == 422
    assert service.received is None


@pytest.mark.anyio
async def test_archive_conversation() -> None:
    service = StubConversationService()
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/conversations/{CONVERSATION_ID}/archive")

    assert response.status_code == 204
    assert response.content == b""
    assert service.received == (PRINCIPAL, str(CONVERSATION_ID), ModelId.HINA)


@pytest.mark.anyio
@pytest.mark.parametrize("legacy_model_id", ["archive", "flagship"])
async def test_legacy_model_id_is_rejected(legacy_model_id: str) -> None:
    service = StubConversationService()
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/conversations",
            json={"input": "こんにちは", "model": legacy_model_id},
        )

    assert response.status_code == 422
    assert service.received is None
