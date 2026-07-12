from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.principal import get_conversation_principal
from app.domain.conversations import (
    Conversation,
    ConversationCreation,
    ConversationPrincipal,
    InferenceRun,
    Message,
    MessageStatus,
    PrincipalKind,
    RunStatus,
    Speaker,
)
from app.main import app
from app.repositories.conversations import ConversationBusyError
from app.services.conversation import get_conversation_service

PRINCIPAL = ConversationPrincipal(
    PrincipalKind.GUEST,
    UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
)
CONVERSATION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
INPUT_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748c")
OUTPUT_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748d")
RUN_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748e")
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
        requested_model="archive",
        resolved_model="pseudo-sodai-archive-v1",
        status=RunStatus.QUEUED,
        created_at=NOW,
    )
    return ConversationCreation(
        conversation=Conversation(
            id=CONVERSATION_ID,
            title="こんにちは",
            model="archive",
            messages=messages,
            active_run=run,
            created_at=NOW,
            updated_at=NOW,
            last_activity_at=NOW,
        ),
        run=run,
    )


class StubConversationService:
    def __init__(self, *, busy: bool = False) -> None:
        self.busy = busy
        self.received: tuple[ConversationPrincipal, str, str] | None = None

    async def create(
        self, principal: ConversationPrincipal, content: str, model: str
    ) -> ConversationCreation:
        self.received = (principal, content, model)
        return creation_fixture()

    async def add_turn(
        self,
        principal: ConversationPrincipal,
        conversation_id: UUID,
        content: str,
        model: str,
    ) -> ConversationCreation:
        if self.busy:
            raise ConversationBusyError
        self.received = (principal, content, model)
        return creation_fixture()


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
            json={"input": "こんにちは", "model": "archive"},
        )

    assert response.status_code == 201
    assert [message["speaker"] for message in response.json()["conversation"]["messages"]] == [
        "partner",
        "sodai",
    ]
    assert response.json()["run"]["resolved_model"] == "pseudo-sodai-archive-v1"
    assert service.received == (PRINCIPAL, "こんにちは", "archive")


@pytest.mark.anyio
async def test_create_turn_reports_active_generation_conflict() -> None:
    app.dependency_overrides[get_conversation_principal] = lambda: PRINCIPAL
    app.dependency_overrides[get_conversation_service] = lambda: StubConversationService(busy=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/conversations/{CONVERSATION_ID}/turns",
            json={"input": "続けましょう", "model": "archive"},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "A response is already being generated"}
