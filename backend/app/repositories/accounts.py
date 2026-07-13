from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts import Account, AccountStatus, ExternalIdentity
from app.models.account import AuthIdentityModel, UserModel


class IdentityAlreadyLinkedError(Exception):
    """Raised when a concurrent request already persisted an identity."""


class AccountRepository(Protocol):
    async def find_by_identity(self, identity: ExternalIdentity) -> Account | None: ...

    async def create_with_identity(self, identity: ExternalIdentity) -> Account: ...

    async def synchronize_identity(self, identity: ExternalIdentity) -> Account: ...

    async def set_display_name(
        self,
        identity: ExternalIdentity,
        display_name: str,
    ) -> Account: ...


class SqlAlchemyAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_identity(self, identity: ExternalIdentity) -> Account | None:
        row = await self._find_row(identity)
        if row is None:
            return None
        user, identity_model = row
        return self._to_account(user, identity_model)

    async def create_with_identity(self, identity: ExternalIdentity) -> Account:
        now = datetime.now(timezone.utc)
        user = UserModel(
            status=AccountStatus.ACTIVE.value,
            display_name=identity.display_name,
        )
        identity_model = AuthIdentityModel(
            user=user,
            issuer=identity.issuer,
            subject=identity.subject,
            email=identity.email,
            email_verified=identity.email_verified,
            display_name=identity.display_name,
            last_seen_at=now,
        )

        try:
            # The savepoint keeps the outer unit of work usable if another first
            # request wins the unique (issuer, subject) race.
            async with self._session.begin_nested():
                self._session.add_all([user, identity_model])
                await self._session.flush()
        except IntegrityError as exc:
            raise IdentityAlreadyLinkedError from exc

        return self._to_account(user, identity_model)

    async def synchronize_identity(self, identity: ExternalIdentity) -> Account:
        row = await self._find_row(identity)
        if row is None:
            raise LookupError("identity is not linked to a SodAI account")

        user, identity_model = row
        identity_model.email = identity.email
        identity_model.email_verified = identity.email_verified
        identity_model.display_name = identity.display_name
        identity_model.last_seen_at = datetime.now(timezone.utc)
        if user.display_name is None and identity.display_name is not None:
            user.display_name = identity.display_name
        await self._session.flush()
        return self._to_account(user, identity_model)

    async def set_display_name(
        self,
        identity: ExternalIdentity,
        display_name: str,
    ) -> Account:
        row = await self._find_row(identity)
        if row is None:
            raise LookupError("identity is not linked to a SodAI account")

        user, identity_model = row
        user.display_name = display_name
        await self._session.flush()
        return self._to_account(user, identity_model)

    async def _find_row(
        self,
        identity: ExternalIdentity,
    ) -> tuple[UserModel, AuthIdentityModel] | None:
        statement = (
            select(UserModel, AuthIdentityModel)
            .join(AuthIdentityModel, AuthIdentityModel.user_id == UserModel.id)
            .where(
                AuthIdentityModel.issuer == identity.issuer,
                AuthIdentityModel.subject == identity.subject,
            )
        )
        result = await self._session.execute(statement)
        return result.one_or_none()

    @staticmethod
    def _to_account(user: UserModel, identity: AuthIdentityModel) -> Account:
        return Account(
            id=user.id,
            status=AccountStatus(user.status),
            display_name=user.display_name,
            email=identity.email,
            email_verified=identity.email_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
