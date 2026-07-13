from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch


class ModelDeploymentError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ModelDeployment:
    model: str
    artifact_id: str

    @property
    def resolved_model(self) -> str:
        return f"{self.model}@{self.artifact_id}"


class ModelDeploymentRegistry:
    def __init__(self, model_root: Path) -> None:
        self._model_root = model_root

    def resolve(self, model: str) -> ModelDeployment:
        path = self._model_root / model / "deployment.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelDeploymentError(f"deployment is unavailable for {model}") from error
        artifact_id = value.get("artifact_id")
        deployed_model = value.get("model")
        if (
            deployed_model != model
            or not isinstance(artifact_id, str)
            or fullmatch(r"[0-9a-f]{16}", artifact_id) is None
        ):
            raise ModelDeploymentError(f"deployment is invalid for {model}")
        return self.resolve_artifact(model, artifact_id)

    def resolve_artifact(self, model: str, artifact_id: str) -> ModelDeployment:
        if fullmatch(r"[0-9a-f]{16}", artifact_id) is None:
            raise ModelDeploymentError(f"artifact id is invalid for {model}")
        path = self._model_root / model / "deployment.json"
        artifact_path = (path.parent / artifact_id).resolve()
        if artifact_path.parent != path.parent.resolve():
            raise ModelDeploymentError(f"deployment escapes model root for {model}")
        manifest_path = artifact_path / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelDeploymentError(f"artifact is unavailable for {model}") from error
        if manifest.get("model") != model or manifest.get("artifact_id") != artifact_id:
            raise ModelDeploymentError(f"artifact manifest is invalid for {model}")
        return ModelDeployment(model=model, artifact_id=artifact_id)
