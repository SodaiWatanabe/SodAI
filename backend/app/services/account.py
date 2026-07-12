from collections.abc import Callable

from app.db.session import get_session_factory
from app.domain.accounts import Account, ExternalIdentity
from app.repositories.accounts import IdentityAlreadyLinkedError
from app.repositories.unit_of_work import AccountUnitOfWork, SqlAlchemyAccountUnitOfWork

AccountUnitOfWorkFactory = Callable[[], AccountUnitOfWork]


class AccountResolutionError(Exception):
    pass


class AccountService:
    def __init__(self, unit_of_work_factory: AccountUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def resolve_authenticated_account(self, identity: ExternalIdentity) -> Account:
        """Resolve or atomically provision the app-owned account for an identity."""

        async with self._unit_of_work_factory() as unit_of_work:
            account = await unit_of_work.accounts.find_by_identity(identity)
            if account is not None:
                account = await unit_of_work.accounts.synchronize_identity(identity)
                await unit_of_work.commit()
                return account

            try:
                account = await unit_of_work.accounts.create_with_identity(identity)
            except IdentityAlreadyLinkedError as exc:
                # A simultaneous first request can win the unique identity insert.
                # Read its result without creating a second SodAI user.
                account = await unit_of_work.accounts.find_by_identity(identity)
                if account is None:
                    raise AccountResolutionError("failed to resolve external identity") from exc
                account = await unit_of_work.accounts.synchronize_identity(identity)

            await unit_of_work.commit()
            return account


def get_account_service() -> AccountService:
    session_factory = get_session_factory()
    return AccountService(lambda: SqlAlchemyAccountUnitOfWork(session_factory))
