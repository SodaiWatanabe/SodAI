import asyncio
from collections.abc import Mapping
from time import monotonic
from typing import Any, Protocol

import httpx
from jwt import PyJWK
from jwt.exceptions import PyJWTError

from app.auth.verifier import TokenVerificationError


class JwksProvider(Protocol):
    async def get_key(self, key_id: str) -> PyJWK:
        """Return the signing key identified by a JWT kid header."""
        ...


class JwksKeyError(TokenVerificationError):
    pass


class RemoteJwksProvider:
    """Small async JWKS client with rotation-aware and negative caching."""

    def __init__(
        self,
        url: str,
        *,
        cache_seconds: int,
        timeout_seconds: float,
        missing_key_cache_seconds: int = 30,
        minimum_refresh_interval_seconds: int = 5,
    ) -> None:
        self._url = url
        self._cache_seconds = cache_seconds
        self._timeout_seconds = timeout_seconds
        self._missing_key_cache_seconds = missing_key_cache_seconds
        self._minimum_refresh_interval_seconds = minimum_refresh_interval_seconds
        self._keys: dict[str, PyJWK] = {}
        self._expires_at = 0.0
        self._last_refresh_at = 0.0
        self._missing_keys: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def get_key(self, key_id: str) -> PyJWK:
        if not key_id or len(key_id) > 256:
            raise JwksKeyError("invalid JWT key id")

        now = monotonic()
        key = self._keys.get(key_id)
        if key is not None and now < self._expires_at:
            return key
        if self._missing_keys.get(key_id, 0.0) > now:
            raise JwksKeyError("JWT signing key not found")

        async with self._lock:
            now = monotonic()
            key = self._keys.get(key_id)
            if key is not None and now < self._expires_at:
                return key
            if self._missing_keys.get(key_id, 0.0) > now:
                raise JwksKeyError("JWT signing key not found")

            # An unknown kid triggers rotation discovery, but never allows a caller
            # to force unbounded outbound requests with random header values.
            if self._keys and now - self._last_refresh_at < self._minimum_refresh_interval_seconds:
                self._remember_missing_key(key_id, now)
                raise JwksKeyError("JWT signing key not found")

            await self._refresh()
            key = self._keys.get(key_id)
            if key is None:
                self._remember_missing_key(key_id, now)
                raise JwksKeyError("JWT signing key not found")
            return key

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(self._url, headers={"Accept": "application/json"})
                response.raise_for_status()
                payload = response.json()
            keys = self._parse_keys(payload)
        except (httpx.HTTPError, ValueError, TypeError, PyJWTError) as exc:
            raise JwksKeyError("unable to load trusted signing keys") from exc

        self._keys = keys
        self._last_refresh_at = monotonic()
        self._expires_at = self._last_refresh_at + self._cache_seconds
        self._missing_keys.clear()

    def _remember_missing_key(self, key_id: str, now: float) -> None:
        if len(self._missing_keys) >= 128:
            self._missing_keys.clear()
        self._missing_keys[key_id] = now + self._missing_key_cache_seconds

    @staticmethod
    def _parse_keys(payload: Any) -> dict[str, PyJWK]:
        if not isinstance(payload, Mapping):
            raise ValueError("JWKS response must be an object")
        raw_keys = payload.get("keys")
        if not isinstance(raw_keys, list) or not raw_keys:
            raise ValueError("JWKS response must contain keys")

        parsed: dict[str, PyJWK] = {}
        for raw_key in raw_keys:
            if not isinstance(raw_key, dict):
                raise ValueError("invalid JWK entry")
            key_id = raw_key.get("kid")
            if not isinstance(key_id, str) or not key_id:
                raise ValueError("JWK is missing kid")
            if key_id in parsed:
                raise ValueError("JWKS contains a duplicate kid")
            parsed[key_id] = PyJWK.from_dict(raw_key)
        return parsed
