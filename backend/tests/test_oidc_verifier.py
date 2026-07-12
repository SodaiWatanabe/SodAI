from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt import PyJWK
from jwt.algorithms import OKPAlgorithm

from app.auth.oidc import OIDCTokenVerifier
from app.auth.verifier import TokenVerificationError

ISSUER = "https://identity.example.test"
AUDIENCE = "https://platform.example.test"
KEY_ID = "test-key"


class StaticJwksProvider:
    def __init__(self, key: PyJWK) -> None:
        self.key = key
        self.requested_key_id: str | None = None

    async def get_key(self, key_id: str) -> PyJWK:
        self.requested_key_id = key_id
        return self.key


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def signing_material() -> tuple[Ed25519PrivateKey, PyJWK]:
    private_key = Ed25519PrivateKey.generate()
    raw_jwk = OKPAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    raw_jwk["kid"] = KEY_ID
    raw_jwk["alg"] = "EdDSA"
    return private_key, PyJWK.from_dict(raw_jwk)


def issue_token(
    private_key: Ed25519PrivateKey,
    **overrides: object,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "external-user-id",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "email": "sodai@example.test",
        "emailVerified": True,
        "name": "蒼大",
    }
    payload.update(overrides)
    return jwt.encode(
        payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": KEY_ID},
    )


@pytest.mark.anyio
async def test_verifies_eddsa_token_and_maps_provider_neutral_identity(
    signing_material: tuple[Ed25519PrivateKey, PyJWK],
) -> None:
    private_key, public_jwk = signing_material
    jwks = StaticJwksProvider(public_jwk)
    verifier = OIDCTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        algorithm="EdDSA",
        jwks_provider=jwks,
        leeway_seconds=0,
    )

    identity = await verifier.verify(issue_token(private_key))

    assert identity.issuer == ISSUER
    assert identity.subject == "external-user-id"
    assert identity.email == "sodai@example.test"
    assert identity.email_verified is True
    assert identity.display_name == "蒼大"
    assert jwks.requested_key_id == KEY_ID


@pytest.mark.anyio
@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"iss": "https://attacker.example.test"},
        {"aud": "another-audience"},
        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        {"sub": ""},
    ],
)
async def test_rejects_invalid_required_claims(
    signing_material: tuple[Ed25519PrivateKey, PyJWK],
    claim_overrides: dict[str, object],
) -> None:
    private_key, public_jwk = signing_material
    verifier = OIDCTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        algorithm="EdDSA",
        jwks_provider=StaticJwksProvider(public_jwk),
        leeway_seconds=0,
    )

    with pytest.raises(TokenVerificationError):
        await verifier.verify(issue_token(private_key, **claim_overrides))


@pytest.mark.anyio
async def test_rejects_token_signed_by_another_key(
    signing_material: tuple[Ed25519PrivateKey, PyJWK],
) -> None:
    _, trusted_jwk = signing_material
    attacker_key = Ed25519PrivateKey.generate()
    verifier = OIDCTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        algorithm="EdDSA",
        jwks_provider=StaticJwksProvider(trusted_jwk),
        leeway_seconds=0,
    )

    with pytest.raises(TokenVerificationError):
        await verifier.verify(issue_token(attacker_key))
