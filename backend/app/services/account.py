from collections.abc import Callable

from app.db.session import get_session_factory
from app.domain.accounts import Account, AccountStatus, ExternalIdentity
from app.repositories.accounts import IdentityAlreadyLinkedError
from app.repositories.unit_of_work import AccountUnitOfWork, SqlAlchemyAccountUnitOfWork

AccountUnitOfWorkFactory = Callable[[], AccountUnitOfWork]


class AccountResolutionError(Exception):
    pass


class InactiveAccountError(Exception):
    pass


class AccountService:
    def __init__(self, unit_of_work_factory: AccountUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def resolve_authenticated_account(self, identity: ExternalIdentity) -> Account:
        """Resolve or atomically provision the app-owned account for an identity."""

        async with self._unit_of_work_factory() as unit_of_work:
            account = await self._resolve(unit_of_work, identity)
            await unit_of_work.commit()
            return account

    async def set_display_name(
        self,
        identity: ExternalIdentity,
        display_name: str,
    ) -> Account:
        normalized_name = display_name.strip()
        if not normalized_name:
            raise ValueError("display name must not be empty")

        async with self._unit_of_work_factory() as unit_of_work:
            account = await self._resolve(unit_of_work, identity)
            if account.status is not AccountStatus.ACTIVE:
                raise InactiveAccountError
            account = await unit_of_work.accounts.set_display_name(
                identity,
                normalized_name,
            )
            await unit_of_work.commit()
            return account

    async def _resolve(
        self,
        unit_of_work: AccountUnitOfWork,
        identity: ExternalIdentity,
    ) -> Account:
        account = await unit_of_work.accounts.find_by_identity(identity)
        if account is not None:
            return await unit_of_work.accounts.synchronize_identity(identity)

        try:
            return await unit_of_work.accounts.create_with_identity(identity)
        except IdentityAlreadyLinkedError as exc:
            account = await unit_of_work.accounts.find_by_identity(identity)
            if account is None:
                raise AccountResolutionError("failed to resolve external identity") from exc
            return await unit_of_work.accounts.synchronize_identity(identity)


def get_account_service() -> AccountService:
    session_factory = get_session_factory()
    return AccountService(lambda: SqlAlchemyAccountUnitOfWork(session_factory))
