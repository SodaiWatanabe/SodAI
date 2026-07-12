from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwks import RemoteJwksProvider
from app.auth.oidc import OIDCTokenVerifier
from app.auth.verifier import TokenVerificationError, TokenVerifier
from app.core.config import get_settings
from app.domain.accounts import ExternalIdentity

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_token_verifier() -> TokenVerifier:
    settings = get_settings()
    jwks_provider = RemoteJwksProvider(
        settings.auth_jwks_url,
        cache_seconds=settings.auth_jwks_cache_seconds,
        timeout_seconds=settings.auth_jwks_timeout_seconds,
    )
    return OIDCTokenVerifier(
        issuer=settings.auth_issuer,
        audience=settings.auth_audience,
        algorithm=settings.auth_jwt_algorithm,
        jwks_provider=jwks_provider,
        leeway_seconds=settings.auth_jwt_leeway_seconds,
    )


async def get_authenticated_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> ExternalIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        return await verifier.verify(credentials.credentials)
    except TokenVerificationError as exc:
        raise _unauthorized() from exc


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
