from types import TracebackType
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.accounts import AccountRepository, SqlAlchemyAccountRepository


class AccountUnitOfWork(Protocol):
    accounts: AccountRepository

    async def __aenter__(self) -> "AccountUnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class SqlAlchemyAccountUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False
        self.accounts: AccountRepository

    async def __aenter__(self) -> "SqlAlchemyAccountUnitOfWork":
        self._session = self._session_factory()
        self.accounts = SqlAlchemyAccountRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work has not been entered")
        await self._session.commit()
        self._committed = True
