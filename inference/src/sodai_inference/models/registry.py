from __future__ import annotations

from pathlib import Path

from sodai_inference.artifacts import ArtifactProfile
from sodai_inference.models.asuka1.profile import ASUKA1_PROFILE
from sodai_inference.models.base import InferenceEngine
from sodai_inference.models.hina.profile import HINA_PROFILE

PROFILES = {
    HINA_PROFILE.model: HINA_PROFILE,
    ASUKA1_PROFILE.model: ASUKA1_PROFILE,
}


def get_model_profile(model: str) -> ArtifactProfile:
    try:
        return PROFILES[model]
    except KeyError as error:
        raise ValueError(f"unsupported inference model: {model}") from error


def load_engine(model: str, artifact_path: Path, device: str) -> InferenceEngine:
    if model == HINA_PROFILE.model:
        from sodai_inference.models.hina import HinaEngine

        return HinaEngine.load(artifact_path, device)
    if model == ASUKA1_PROFILE.model:
        from sodai_inference.models.asuka1 import Asuka1Engine

        return Asuka1Engine.load(artifact_path, device)
    raise ValueError(f"unsupported inference model: {model}")
