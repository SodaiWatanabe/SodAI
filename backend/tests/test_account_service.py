from datetime import datetime, timezone
from types import TracebackType
from uuid import UUID

import pytest

from app.domain.accounts import Account, AccountStatus, ExternalIdentity
from app.repositories.accounts import IdentityAlreadyLinkedError
from app.services.account import AccountResolutionError, AccountService

NOW = datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc)
IDENTITY = ExternalIdentity(
    issuer="https://identity.example.test",
    subject="subject-1",
    email="sodai@example.test",
    email_verified=True,
    display_name="蒼大",
)
ACCOUNT = Account(
    id=UUID("018f96d4-7c48-7c27-a71f-591e3cb8748a"),
    status=AccountStatus.ACTIVE,
    display_name="蒼大",
    email="sodai@example.test",
    email_verified=True,
    created_at=NOW,
    updated_at=NOW,
)


class FakeAccountRepository:
    def __init__(self, existing: Account | None = None, *, race: bool = False) -> None:
        self.existing = existing
        self.race = race
        self.created = 0
        self.synchronized = 0
        self._find_count = 0

    async def find_by_identity(self, identity: ExternalIdentity) -> Account | None:
        assert identity == IDENTITY
        self._find_count += 1
        if self.race and self._find_count > 1:
            return ACCOUNT
        return self.existing

    async def create_with_identity(self, identity: ExternalIdentity) -> Account:
        assert identity == IDENTITY
        self.created += 1
        if self.race:
            raise IdentityAlreadyLinkedError
        return ACCOUNT

    async def synchronize_identity(self, identity: ExternalIdentity) -> Account:
        assert identity == IDENTITY
        self.synchronized += 1
        return ACCOUNT


class FakeUnitOfWork:
    def __init__(self, accounts: FakeAccountRepository) -> None:
        self.accounts = accounts
        self.committed = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_first_access_creates_app_owned_account() -> None:
    repository = FakeAccountRepository()
    unit_of_work = FakeUnitOfWork(repository)
    service = AccountService(lambda: unit_of_work)

    account = await service.resolve_authenticated_account(IDENTITY)

    assert account == ACCOUNT
    assert repository.created == 1
    assert repository.synchronized == 0
    assert unit_of_work.committed


@pytest.mark.anyio
async def test_existing_identity_is_synchronized() -> None:
    repository = FakeAccountRepository(existing=ACCOUNT)
    unit_of_work = FakeUnitOfWork(repository)
    service = AccountService(lambda: unit_of_work)

    account = await service.resolve_authenticated_account(IDENTITY)

    assert account == ACCOUNT
    assert repository.created == 0
    assert repository.synchronized == 1
    assert unit_of_work.committed


@pytest.mark.anyio
async def test_concurrent_first_access_reuses_winning_account() -> None:
    repository = FakeAccountRepository(race=True)
    unit_of_work = FakeUnitOfWork(repository)
    service = AccountService(lambda: unit_of_work)

    account = await service.resolve_authenticated_account(IDENTITY)

    assert account == ACCOUNT
    assert repository.created == 1
    assert repository.synchronized == 1
    assert unit_of_work.committed


@pytest.mark.anyio
async def test_unexplained_identity_constraint_failure_is_not_silenced() -> None:
    repository = FakeAccountRepository(race=True)
    repository.find_by_identity = _always_missing  # type: ignore[method-assign]
    unit_of_work = FakeUnitOfWork(repository)
    service = AccountService(lambda: unit_of_work)

    with pytest.raises(AccountResolutionError):
        await service.resolve_authenticated_account(IDENTITY)

    assert not unit_of_work.committed


async def _always_missing(identity: ExternalIdentity) -> None:
    assert identity == IDENTITY
    return None
