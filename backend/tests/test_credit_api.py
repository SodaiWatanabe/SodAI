from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.accounts import Account, AccountStatus
from app.domain.credits import (
    CREDIT_ASSET_CODE,
    CREDIT_SCALE,
    CreditBalance,
    CreditSourceKind,
    CreditTransaction,
    CreditTransactionKind,
    CreditTransactionPage,
)
from app.main import app
from app.routers.account import get_current_account
from app.services.credits import get_credit_service

USER_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a")
TRANSACTION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
NOW = datetime(2026, 7, 13, 15, 0, tzinfo=timezone.utc)


class StubCreditService:
    received: tuple[UUID, int, str | None] | None = None

    async def balance(self, user_id: UUID) -> CreditBalance:
        assert user_id == USER_ID
        return CreditBalance(CREDIT_ASSET_CODE, CREDIT_SCALE, 3_000_000, 1_000_000)

    async def transactions(
        self, user_id: UUID, *, limit: int, cursor: str | None
    ) -> CreditTransactionPage:
        self.received = (user_id, limit, cursor)
        return CreditTransactionPage(
            (
                CreditTransaction(
                    id=TRANSACTION_ID,
                    kind=CreditTransactionKind.GRANT,
                    available_delta=3_000_000,
                    reserved_delta=0,
                    source_kind=CreditSourceKind.ADMIN,
                    expires_at=None,
                    created_at=NOW,
                ),
            ),
            "next",
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def account() -> Account:
    return Account(
        id=USER_ID,
        status=AccountStatus.ACTIVE,
        display_name="Credit owner",
        email=None,
        email_verified=False,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.anyio
async def test_credit_balance_is_account_scoped() -> None:
    app.dependency_overrides[get_current_account] = account
    app.dependency_overrides[get_credit_service] = StubCreditService
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/credits")

    assert response.status_code == 200
    assert response.json() == {
        "asset_code": "sodai-credit",
        "scale": 1_000_000,
        "available": 3_000_000,
        "reserved": 1_000_000,
    }


@pytest.mark.anyio
async def test_credit_transaction_history_uses_an_opaque_cursor() -> None:
    service = StubCreditService()
    app.dependency_overrides[get_current_account] = account
    app.dependency_overrides[get_credit_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/credits/transactions",
            params={"limit": 25, "cursor": "opaque"},
        )

    assert response.status_code == 200
    assert service.received == (USER_ID, 25, "opaque")
    assert response.json() == {
        "items": [
            {
                "id": str(TRANSACTION_ID),
                "kind": "grant",
                "available_delta": 3_000_000,
                "reserved_delta": 0,
                "source_kind": "admin",
                "expires_at": None,
                "created_at": "2026-07-13T15:00:00Z",
            }
        ],
        "next_cursor": "next",
    }


@pytest.mark.anyio
async def test_credit_endpoints_require_an_authenticated_account() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/credits")

    assert response.status_code == 401
