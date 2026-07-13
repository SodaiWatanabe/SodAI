from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_token_verifier
from app.auth.verifier import TokenVerificationError
from app.domain.accounts import Account, AccountStatus, ExternalIdentity
from app.main import app
from app.services.account import InactiveAccountError, get_account_service

ACCOUNT_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a")
NOW = datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc)


class StubVerifier:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def verify(self, token: str) -> ExternalIdentity:
        if self.fail or token != "valid-token":
            raise TokenVerificationError
        return ExternalIdentity(
            issuer="https://identity.example.test",
            subject="provider-user-id",
            email="sodai@example.test",
            email_verified=True,
            display_name="蒼大",
        )


class StubAccountService:
    def __init__(self) -> None:
        self.received_identity: ExternalIdentity | None = None

    async def resolve_authenticated_account(self, identity: ExternalIdentity) -> Account:
        self.received_identity = identity
        return Account(
            id=ACCOUNT_ID,
            status=AccountStatus.ACTIVE,
            display_name=identity.display_name,
            email=identity.email,
            email_verified=identity.email_verified,
            created_at=NOW,
            updated_at=NOW,
        )

    async def set_display_name(
        self,
        identity: ExternalIdentity,
        display_name: str,
    ) -> Account:
        self.received_identity = identity
        return Account(
            id=ACCOUNT_ID,
            status=AccountStatus.ACTIVE,
            display_name=display_name,
            email=identity.email,
            email_verified=identity.email_verified,
            created_at=NOW,
            updated_at=NOW,
        )


class InactiveAccountService(StubAccountService):
    async def set_display_name(
        self,
        identity: ExternalIdentity,
        display_name: str,
    ) -> Account:
        raise InactiveAccountError


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_account_me_resolves_verified_identity() -> None:
    service = StubAccountService()
    app.dependency_overrides[get_token_verifier] = lambda: StubVerifier()
    app.dependency_overrides[get_account_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/account/me",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(ACCOUNT_ID),
        "status": "active",
        "display_name": "蒼大",
        "email": "sodai@example.test",
        "email_verified": True,
        "created_at": "2026-07-12T09:00:00Z",
        "updated_at": "2026-07-12T09:00:00Z",
    }
    assert service.received_identity is not None
    assert service.received_identity.subject == "provider-user-id"


@pytest.mark.anyio
async def test_account_me_requires_bearer_token() -> None:
    app.dependency_overrides[get_token_verifier] = lambda: StubVerifier()
    app.dependency_overrides[get_account_service] = lambda: StubAccountService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/account/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.anyio
async def test_account_me_rejects_invalid_token_without_leaking_reason() -> None:
    app.dependency_overrides[get_token_verifier] = lambda: StubVerifier(fail=True)
    app.dependency_overrides[get_account_service] = lambda: StubAccountService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/account/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.anyio
async def test_account_profile_can_be_completed() -> None:
    service = StubAccountService()
    app.dependency_overrides[get_token_verifier] = lambda: StubVerifier()
    app.dependency_overrides[get_account_service] = lambda: service

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            "/api/v1/account/me",
            headers={"Authorization": "Bearer valid-token"},
            json={"display_name": "雛"},
        )

    assert response.status_code == 200
    assert response.json()["display_name"] == "雛"
    assert service.received_identity is not None


@pytest.mark.anyio
async def test_account_profile_rejects_blank_display_name() -> None:
    app.dependency_overrides[get_token_verifier] = lambda: StubVerifier()
    app.dependency_overrides[get_account_service] = lambda: StubAccountService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            "/api/v1/account/me",
            headers={"Authorization": "Bearer valid-token"},
            json={"display_name": "   "},
        )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_inactive_account_cannot_update_profile() -> None:
    app.dependency_overrides[get_token_verifier] = lambda: StubVerifier()
    app.dependency_overrides[get_account_service] = lambda: InactiveAccountService()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.patch(
            "/api/v1/account/me",
            headers={"Authorization": "Bearer valid-token"},
            json={"display_name": "雛"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Account is not active"}
