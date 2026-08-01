from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.principal import get_principal
from app.domain.humans import (
    HumanAnswerDetail,
    HumanAnswerPage,
    HumanAnswerSummary,
    HumanContextEntry,
)
from app.domain.principals import Principal, PrincipalKind
from app.domain.reasoning import ReasoningEffort
from app.domain.threads import ActorKind
from app.main import app
from app.repositories.human_answers import HumanAnswerNotFoundError
from app.services.human_answers import get_human_answer_history_service

USER_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a")
EXECUTION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748f")
NOW = datetime(2026, 8, 1, 12, 34, tzinfo=timezone.utc)


class StubHumanAnswerHistoryService:
    def __init__(self, *, missing: bool = False, invalid_cursor: bool = False) -> None:
        self.missing = missing
        self.invalid_cursor = invalid_cursor
        self.page_received: tuple[UUID, int, str | None] | None = None
        self.get_received: tuple[UUID, UUID] | None = None

    async def page(
        self,
        user_id: UUID,
        *,
        limit: int,
        cursor: str | None,
    ) -> HumanAnswerPage:
        if self.invalid_cursor:
            raise ValueError("invalid Human answer cursor")
        self.page_received = (user_id, limit, cursor)
        return HumanAnswerPage(
            (
                HumanAnswerSummary(
                    EXECUTION_ID,
                    "Human Standard",
                    ReasoningEffort.MEDIUM,
                    "回答履歴のPrompt",
                    NOW,
                ),
            ),
            "next",
        )

    async def get(self, user_id: UUID, execution_id: UUID) -> HumanAnswerDetail:
        if self.missing:
            raise HumanAnswerNotFoundError
        self.get_received = (user_id, execution_id)
        return HumanAnswerDetail(
            EXECUTION_ID,
            "Human Standard",
            ReasoningEffort.MEDIUM,
            NOW,
            (HumanContextEntry(ActorKind.HUMAN, "回答履歴のPrompt"),),
            "回答履歴の回答",
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_human_answer_history_is_scoped_to_the_authenticated_user() -> None:
    service = StubHumanAnswerHistoryService()
    app.dependency_overrides[get_principal] = lambda: Principal(
        PrincipalKind.USER,
        USER_ID,
    )
    app.dependency_overrides[get_human_answer_history_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        page = await client.get(
            "/api/v1/human/answers",
            params={"limit": 12, "cursor": "opaque"},
        )
        detail = await client.get(f"/api/v1/human/answers/{EXECUTION_ID}")

    assert page.status_code == 200
    assert page.headers["cache-control"] == "private, no-store"
    assert page.json() == {
        "items": [
            {
                "execution_id": str(EXECUTION_ID),
                "answerer_name": "Human Standard",
                "reasoning_effort": "medium",
                "prompt_preview": "回答履歴のPrompt",
                "answered_at": NOW.isoformat().replace("+00:00", "Z"),
            }
        ],
        "next_cursor": "next",
    }
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "private, no-store"
    assert detail.json() == {
        "execution_id": str(EXECUTION_ID),
        "answerer_name": "Human Standard",
        "reasoning_effort": "medium",
        "answered_at": NOW.isoformat().replace("+00:00", "Z"),
        "context": [{"author_kind": "human", "content": "回答履歴のPrompt"}],
        "answer": "回答履歴の回答",
    }
    assert service.page_received == (USER_ID, 12, "opaque")
    assert service.get_received == (USER_ID, EXECUTION_ID)


@pytest.mark.anyio
async def test_human_answer_history_hides_missing_answers_and_rejects_bad_cursors() -> None:
    service = StubHumanAnswerHistoryService(missing=True, invalid_cursor=True)
    app.dependency_overrides[get_principal] = lambda: Principal(
        PrincipalKind.USER,
        USER_ID,
    )
    app.dependency_overrides[get_human_answer_history_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing = await client.get(f"/api/v1/human/answers/{EXECUTION_ID}")
        invalid_cursor = await client.get(
            "/api/v1/human/answers",
            params={"cursor": "invalid"},
        )

    assert missing.status_code == 404
    assert invalid_cursor.status_code == 422


@pytest.mark.anyio
async def test_human_answer_history_requires_a_user_principal() -> None:
    service = StubHumanAnswerHistoryService()
    app.dependency_overrides[get_principal] = lambda: Principal(
        PrincipalKind.GUEST,
        USER_ID,
    )
    app.dependency_overrides[get_human_answer_history_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/human/answers")

    assert response.status_code == 401
    assert service.page_received is None
