from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.principal import get_conversation_principal
from app.domain.accounts import Account, AccountStatus, ExternalIdentity

ACCOUNT_ID = UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a")
NOW = datetime(2026, 7, 12, 13, 0, tzinfo=timezone.utc)
IDENTITY = ExternalIdentity(issuer="https://issuer.test", subject="subject")


class StubVerifier:
    async def verify(self, token: str) -> ExternalIdentity:
        assert token == "token"
        return IDENTITY


class StubAccountService:
    async def resolve_authenticated_account(self, identity: ExternalIdentity) -> Account:
        assert identity == IDENTITY
        return Account(
            id=ACCOUNT_ID,
            status=AccountStatus.SUSPENDED,
            display_name=None,
            email=None,
            email_verified=False,
            created_at=NOW,
            updated_at=NOW,
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_suspended_account_cannot_become_conversation_principal() -> None:
    request = Request({"type": "http", "headers": []})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with pytest.raises(HTTPException) as captured:
        await get_conversation_principal(
            request=request,
            response=Response(),
            credentials=credentials,
            verifier=StubVerifier(),
            account_service=StubAccountService(),
        )

    assert captured.value.status_code == 403
    assert captured.value.detail == "Account is not active"
