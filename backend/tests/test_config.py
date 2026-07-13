from pathlib import Path

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


def test_model_root_uses_the_shared_environment_name(monkeypatch) -> None:
    monkeypatch.setenv("SODAI_MODEL_ROOT", "/srv/sodai/models")

    assert Settings().model_root == Path("/srv/sodai/models")


def test_relative_model_root_is_resolved_from_the_repository(monkeypatch) -> None:
    monkeypatch.setenv("SODAI_MODEL_ROOT", "./var/models")

    assert Settings().model_root == Path(__file__).resolve().parents[2] / "var" / "models"


def test_inference_timeout_cannot_expire_before_crash_reclaim() -> None:
    with pytest.raises(ValidationError):
        Settings(inference_job_timeout_seconds=119)
