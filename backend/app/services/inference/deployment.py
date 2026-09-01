from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from re import fullmatch


class ModelDeploymentError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ModelDeployment:
    deployment_name: str
    model: str
    artifact_id: str

    @property
    def resolved_model(self) -> str:
        return f"{self.model}@{self.artifact_id}"


class ModelDeploymentRegistry:
    def __init__(self, model_root: Path) -> None:
        self._model_root = model_root

    def resolve(self, deployment_name: str) -> ModelDeployment:
        if not _valid_name(deployment_name):
            raise ModelDeploymentError(f"deployment name is invalid: {deployment_name}")
        path = self._model_root / "deployments" / f"{deployment_name}.json"
        legacy = False
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            legacy = True
            path = self._model_root / deployment_name / "deployment.json"
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ModelDeploymentError(
                    f"deployment is unavailable for {deployment_name}"
                ) from error
        except (OSError, json.JSONDecodeError) as error:
            raise ModelDeploymentError(
                f"deployment is unavailable for {deployment_name}"
            ) from error
        if not isinstance(value, dict):
            raise ModelDeploymentError(f"deployment is invalid for {deployment_name}")
        artifact_id = value.get("artifact_id")
        deployed_model = value.get("model")
        deployed_name = value.get("deployment", deployment_name if legacy else None)
        if (
            (not legacy and value.get("schema_version") != 1)
            or deployed_name != deployment_name
            or not isinstance(deployed_model, str)
            or not _valid_name(deployed_model)
            or not isinstance(artifact_id, str)
            or fullmatch(r"[0-9a-f]{16}", artifact_id) is None
        ):
            raise ModelDeploymentError(f"deployment is invalid for {deployment_name}")
        return self.resolve_artifact(
            deployed_model,
            artifact_id,
            deployment_name=deployment_name,
        )

    def resolve_artifact(
        self,
        model: str,
        artifact_id: str,
        *,
        deployment_name: str | None = None,
    ) -> ModelDeployment:
        if not _valid_name(model):
            raise ModelDeploymentError(f"model is invalid: {model}")
        if fullmatch(r"[0-9a-f]{16}", artifact_id) is None:
            raise ModelDeploymentError(f"artifact id is invalid for {model}")
        runtime_root = self._model_root / model
        artifact_path = (runtime_root / artifact_id).resolve()
        if artifact_path.parent != runtime_root.resolve():
            raise ModelDeploymentError(f"deployment escapes model root for {model}")
        manifest_path = artifact_path / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelDeploymentError(f"artifact is unavailable for {model}") from error
        if manifest.get("model") != model or manifest.get("artifact_id") != artifact_id:
            raise ModelDeploymentError(f"artifact manifest is invalid for {model}")
        return ModelDeployment(
            deployment_name=deployment_name or model,
            model=model,
            artifact_id=artifact_id,
        )


def _valid_name(value: str) -> bool:
    return fullmatch(r"[a-z0-9][a-z0-9.-]{0,63}", value) is not None
