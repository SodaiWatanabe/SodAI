from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.accounts import Account, AccountStatus
from app.domain.credits import (
    CREDIT_ASSET_CODE,
    CREDIT_SCALE,
    CreditOverview,
    CreditSourceKind,
    CreditTransaction,
    CreditTransactionKind,
    CreditTransactionPage,
    FreeCreditAllowance,
)
from app.main import app
from app.routers.account import get_current_account
from app.services.credits import get_credit_service

USER_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a")
TRANSACTION_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748b")
NOW = datetime(2026, 7, 13, 15, 0, tzinfo=timezone.utc)


class StubCreditService:
    received: tuple[UUID, int, str | None] | None = None
    balance_calls = 0

    async def balance(self, user_id: UUID) -> CreditOverview:
        self.balance_calls += 1
        assert user_id == USER_ID
        return CreditOverview(
            CREDIT_ASSET_CODE,
            CREDIT_SCALE,
            3_000_000,
            1_000_000,
            FreeCreditAllowance(
                limit=20_000_000,
                used=16_000_000,
                reserved=1_000_000,
                remaining=3_000_000,
                starts_at=NOW,
                expires_at=datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc),
            ),
        )

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


class DormantCreditService(StubCreditService):
    async def balance(self, user_id: UUID) -> CreditOverview:
        overview = await super().balance(user_id)
        return CreditOverview(
            asset_code=overview.asset_code,
            scale=overview.scale,
            available=0,
            reserved=0,
            free_allowance=None,
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
        "free_allowance": {
            "limit": 20_000_000,
            "used": 16_000_000,
            "reserved": 1_000_000,
            "remaining": 3_000_000,
            "starts_at": "2026-07-13T15:00:00Z",
            "expires_at": "2026-07-20T15:00:00Z",
        },
    }
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.anyio
async def test_dormant_credit_balance_has_no_synthetic_cycle() -> None:
    app.dependency_overrides[get_current_account] = account
    app.dependency_overrides[get_credit_service] = DormantCreditService
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/credits")

    assert response.status_code == 200
    assert response.json() == {
        "asset_code": "sodai-credit",
        "scale": 1_000_000,
        "available": 0,
        "reserved": 0,
        "free_allowance": None,
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
    assert response.headers["cache-control"] == "private, no-store"
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
@pytest.mark.parametrize(
    "path",
    ("/api/v1/credits", "/api/v1/credits/transactions"),
)
async def test_credit_endpoints_require_an_authenticated_account(path: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 401


@pytest.mark.anyio
async def test_inactive_account_cannot_read_credits() -> None:
    inactive = account()
    inactive = Account(
        id=inactive.id,
        status=AccountStatus.SUSPENDED,
        display_name=inactive.display_name,
        email=inactive.email,
        email_verified=inactive.email_verified,
        created_at=inactive.created_at,
        updated_at=inactive.updated_at,
    )
    app.dependency_overrides[get_current_account] = lambda: inactive
    service = StubCreditService()
    app.dependency_overrides[get_credit_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        balance_response = await client.get("/api/v1/credits")
        transactions_response = await client.get("/api/v1/credits/transactions")

    assert balance_response.status_code == 403
    assert transactions_response.status_code == 403
    assert service.balance_calls == 0
    assert service.received is None
