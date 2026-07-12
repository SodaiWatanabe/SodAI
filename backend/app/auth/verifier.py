from typing import Protocol

from app.domain.accounts import ExternalIdentity


class TokenVerificationError(Exception):
    """Raised when a bearer token cannot establish a trusted identity."""


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> ExternalIdentity:
        """Verify a token and return provider-neutral identity claims."""
        ...
