from __future__ import annotations

import argparse
import asyncio
import json
import os
import stat
from pathlib import Path
from re import fullmatch

from redis.asyncio import Redis

from sodai_inference.artifacts import ArtifactManifest, sha256_file, sha256_tree
from sodai_inference.config import Settings
from sodai_inference.models.registry import get_model_profile


def resolve_artifact(
    model_root: Path,
    model: str,
    artifact_id: str | None = None,
    *,
    deployment_name: str | None = None,
) -> Path:
    get_model_profile(model)
    if artifact_id is None:
        deployment_name = deployment_name or model
        value = _read_deployment(model_root, deployment_name)
        artifact_id = value.get("artifact_id")
        if value.get("model") != model or not isinstance(artifact_id, str):
            raise ValueError(f"{deployment_name} deployment must contain artifact_id")
    artifact_path = _artifact_path(model_root / model, artifact_id)
    if not artifact_path.is_dir():
        raise FileNotFoundError(f"{model} artifact is missing: {artifact_path}")
    return artifact_path


def activate_deployment(
    model_root: Path,
    deployment_name: str,
    model: str,
    artifact_id: str,
) -> Path:
    _validate_deployment_name(deployment_name)
    profile = get_model_profile(model)
    runtime_root = model_root / model
    artifact_path = _artifact_path(runtime_root, artifact_id)
    manifest = ArtifactManifest.load(artifact_path / "manifest.json")
    manifest.validate(profile)
    if manifest.artifact_id != artifact_id:
        raise ValueError(f"{model} artifact ID does not match its manifest")
    if sha256_file(artifact_path / "model.safetensors") != manifest.checkpoint_sha256:
        raise ValueError(f"{model} artifact weights are corrupted")
    if sha256_file(artifact_path / "model_config.json") != manifest.model_config_sha256:
        raise ValueError(f"{model} artifact config is corrupted")
    if sha256_tree(artifact_path / "tokenizer") != manifest.tokenizer_sha256:
        raise ValueError(f"{model} artifact tokenizer is corrupted")

    deployments_root = model_root / "deployments"
    deployments_root.mkdir(parents=True, exist_ok=True)
    deployment_path = deployments_root / f"{deployment_name}.json"
    temporary = deployment_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "deployment": deployment_name,
                "model": model,
                "artifact_id": artifact_id,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, deployment_path)
    _grant_model_group_read_access(model_root)
    return artifact_path


def activate_artifact(model_root: Path, model: str, artifact_id: str) -> Path:
    return activate_deployment(model_root, model, model, artifact_id)


def _read_deployment(model_root: Path, deployment_name: str) -> dict[str, object]:
    _validate_deployment_name(deployment_name)
    path = model_root / "deployments" / f"{deployment_name}.json"
    legacy = False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        legacy = True
        legacy_path = model_root / deployment_name / "deployment.json"
        value = json.loads(legacy_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"deployment is invalid for {deployment_name}")
        if "deployment" not in value:
            value["deployment"] = deployment_name
    if not isinstance(value, dict):
        raise ValueError(f"deployment is invalid for {deployment_name}")
    if not legacy and value.get("schema_version") != 1:
        raise ValueError(f"deployment schema is invalid for {deployment_name}")
    if value.get("deployment") != deployment_name:
        raise ValueError(f"deployment name does not match {deployment_name}")
    return value


def _validate_deployment_name(deployment_name: str) -> None:
    if fullmatch(r"[a-z0-9][a-z0-9.-]{0,63}", deployment_name) is None:
        raise ValueError("model deployment contains an invalid deployment name")


def _artifact_path(runtime_root: Path, artifact_id: str) -> Path:
    if fullmatch(r"[0-9a-f]{16}", artifact_id) is None:
        raise ValueError("model deployment contains an invalid artifact_id")
    artifact_path = (runtime_root / artifact_id).resolve()
    if artifact_path.parent != runtime_root.resolve():
        raise ValueError("model artifact must be contained by the model root")
    return artifact_path


def _grant_model_group_read_access(model_root: Path) -> None:
    for path in (model_root, *model_root.rglob("*")):
        mode = path.stat().st_mode & ~(stat.S_IWGRP | stat.S_IRWXO)
        mode |= stat.S_IRGRP
        if path.is_dir():
            mode |= stat.S_IXGRP
        path.chmod(mode)


def _main(deployment_name: str, model: str) -> None:
    parser = argparse.ArgumentParser(
        f"Promote an immutable {model} artifact for {deployment_name}"
    )
    parser.add_argument("artifact_id")
    parser.add_argument(
        "--model-root",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    path = asyncio.run(
        _activate_ready_artifact(
            deployment_name,
            model,
            args.artifact_id,
            args.model_root,
        )
    )
    print(f"{deployment_name} deployment: {path}")


async def _activate_ready_artifact(
    deployment_name: str,
    model: str,
    artifact_id: str,
    model_root: Path | None,
) -> Path:
    settings = Settings.from_env()
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
    )
    try:
        ready_key = settings.inference_keys.worker_readiness(model, artifact_id)
        if await redis.get(ready_key) is None:
            raise RuntimeError(f"{model} worker is not ready for artifact {artifact_id}")
    finally:
        await redis.aclose()
    return activate_deployment(
        model_root.resolve() if model_root is not None else settings.model_root,
        deployment_name,
        model,
        artifact_id,
    )


def resolve_hina_artifact(model_root: Path, artifact_id: str | None = None) -> Path:
    return resolve_artifact(model_root, "hina", artifact_id)


def activate_hina_artifact(model_root: Path, artifact_id: str) -> Path:
    return activate_artifact(model_root, "hina", artifact_id)


def main() -> None:
    _main("hina", "hina")


def main_asuka1() -> None:
    _main("asuka-1", "asuka-1")


def main_asuka11() -> None:
    _main("asuka-1.1", "asuka-1")


if __name__ == "__main__":
    main()
