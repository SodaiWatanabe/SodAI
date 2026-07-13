import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.domain.principals import Principal, PrincipalKind
from app.models.platform import GuestSessionModel

GUEST_COOKIE_NAME = "sodai_guest"
GUEST_TTL = timedelta(days=90)


class GuestSessionService:
    async def resolve(self, raw_token: str | None, response: Response) -> Principal:
        now = datetime.now(timezone.utc)
        async with get_session_factory()() as session:
            guest = None
            if raw_token:
                guest = await session.scalar(
                    select(GuestSessionModel).where(
                        GuestSessionModel.token_hash == _hash_token(raw_token),
                        GuestSessionModel.expires_at > now,
                    )
                )
            if guest is None:
                raw_token = secrets.token_urlsafe(32)
                guest = GuestSessionModel(
                    token_hash=_hash_token(raw_token),
                    expires_at=now + GUEST_TTL,
                    last_seen_at=now,
                )
                session.add(guest)
                await session.commit()
                response.set_cookie(
                    GUEST_COOKIE_NAME,
                    raw_token,
                    max_age=int(GUEST_TTL.total_seconds()),
                    httponly=True,
                    samesite="lax",
                    secure=get_settings().guest_cookie_secure,
                    path="/",
                )
            else:
                guest.last_seen_at = now
                await session.commit()
            return Principal(PrincipalKind.GUEST, guest.id)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


guest_session_service = GuestSessionService()
