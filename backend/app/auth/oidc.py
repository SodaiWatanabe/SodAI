from collections.abc import Mapping
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from app.auth.jwks import JwksProvider
from app.auth.verifier import TokenVerificationError, TokenVerifier
from app.domain.accounts import ExternalIdentity


class StandardIdentityClaimsMapper:
    """Map common OIDC claim spellings into the SodAI identity boundary."""

    def map(self, claims: Mapping[str, Any]) -> ExternalIdentity:
        issuer = self._required_string(claims, "iss")
        subject = self._required_string(claims, "sub")
        email = self._optional_string(claims, "email")
        display_name = self._optional_string(claims, "name")

        raw_email_verified = claims.get("email_verified", claims.get("emailVerified", False))
        email_verified = self._boolean(raw_email_verified, "email verification")

        return ExternalIdentity(
            issuer=issuer,
            subject=subject,
            email=email,
            email_verified=email_verified,
            display_name=display_name,
        )

    @staticmethod
    def _required_string(claims: Mapping[str, Any], name: str) -> str:
        value = claims.get(name)
        if not isinstance(value, str) or not value.strip():
            raise TokenVerificationError(f"JWT claim {name} must be a non-empty string")
        return value

    @staticmethod
    def _optional_string(claims: Mapping[str, Any], name: str) -> str | None:
        value = claims.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise TokenVerificationError(f"JWT claim {name} must be a string")
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _boolean(value: Any, description: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise TokenVerificationError(f"JWT {description} claim must be boolean")


class OIDCTokenVerifier(TokenVerifier):
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        algorithm: str,
        jwks_provider: JwksProvider,
        leeway_seconds: int = 30,
        claims_mapper: StandardIdentityClaimsMapper | None = None,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm
        self._jwks_provider = jwks_provider
        self._leeway_seconds = leeway_seconds
        self._claims_mapper = claims_mapper or StandardIdentityClaimsMapper()

    async def verify(self, token: str) -> ExternalIdentity:
        try:
            header = jwt.get_unverified_header(token)
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise TokenVerificationError("malformed bearer token") from exc

        if header.get("alg") != self._algorithm:
            raise TokenVerificationError("JWT signing algorithm is not allowed")
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id:
            raise TokenVerificationError("JWT header is missing kid")

        signing_key = await self._jwks_provider.get_key(key_id)
        if signing_key.algorithm_name != self._algorithm:
            raise TokenVerificationError("JWK algorithm does not match the JWT header")
        try:
            claims = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except InvalidTokenError as exc:
            raise TokenVerificationError("bearer token verification failed") from exc

        return self._claims_mapper.map(claims)
