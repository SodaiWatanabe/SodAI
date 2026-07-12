import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_must_use_async_postgresql() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+aiosqlite:///:memory:")


@pytest.mark.parametrize("algorithm", ["HS256", "none"])
def test_symmetric_or_unsigned_jwt_algorithms_are_rejected(algorithm: str) -> None:
    with pytest.raises(ValidationError):
        Settings(auth_jwt_algorithm=algorithm)
