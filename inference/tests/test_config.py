from pathlib import Path

import pytest

from sodai_inference.config import Settings
from sodai_inference.models.registry import get_model_profile, load_engine


def test_default_worker_uses_the_public_asuka_deployment(monkeypatch) -> None:
    monkeypatch.delenv("SODAI_INFERENCE_MODEL", raising=False)
    monkeypatch.delenv("SODAI_INFERENCE_DEPLOYMENT", raising=False)
    settings = Settings.from_env()
    assert settings.model_name == "asuka-1"
    assert settings.deployment_name == "asuka-1.1"


def test_retired_model_cannot_be_loaded() -> None:
    with pytest.raises(ValueError, match="unsupported inference model"):
        get_model_profile("hina")
    with pytest.raises(ValueError, match="unsupported inference model"):
        load_engine("hina", Path("/unused"), "cpu")
