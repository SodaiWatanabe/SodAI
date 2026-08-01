from __future__ import annotations

import argparse
import asyncio
import json
import os
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
) -> Path:
    get_model_profile(model)
    deployment_path = model_root / model / "deployment.json"
    if artifact_id is None:
        value = json.loads(deployment_path.read_text(encoding="utf-8"))
        artifact_id = value.get("artifact_id")
        if value.get("model") != model or not isinstance(artifact_id, str):
            raise ValueError(f"{model} deployment must contain artifact_id")
    artifact_path = _artifact_path(deployment_path.parent, artifact_id)
    if not artifact_path.is_dir():
        raise FileNotFoundError(f"{model} artifact is missing: {artifact_path}")
    return artifact_path


def activate_artifact(model_root: Path, model: str, artifact_id: str) -> Path:
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

    deployment_path = runtime_root / "deployment.json"
    temporary = deployment_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({"model": model, "artifact_id": artifact_id}, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, deployment_path)
    return artifact_path


def _artifact_path(runtime_root: Path, artifact_id: str) -> Path:
    if fullmatch(r"[0-9a-f]{16}", artifact_id) is None:
        raise ValueError("model deployment contains an invalid artifact_id")
    artifact_path = (runtime_root / artifact_id).resolve()
    if artifact_path.parent != runtime_root.resolve():
        raise ValueError("model artifact must be contained by the model root")
    return artifact_path


def _main(model: str) -> None:
    parser = argparse.ArgumentParser(f"Promote an immutable {model} artifact")
    parser.add_argument("artifact_id")
    parser.add_argument(
        "--model-root",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    path = asyncio.run(
        _activate_ready_artifact(model, args.artifact_id, args.model_root)
    )
    print(f"{model} deployment: {path}")


async def _activate_ready_artifact(
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
    return activate_artifact(
        model_root.resolve() if model_root is not None else settings.model_root,
        model,
        artifact_id,
    )


def resolve_hina_artifact(model_root: Path, artifact_id: str | None = None) -> Path:
    return resolve_artifact(model_root, "hina", artifact_id)


def activate_hina_artifact(model_root: Path, artifact_id: str) -> Path:
    return activate_artifact(model_root, "hina", artifact_id)


def main() -> None:
    _main("hina")


def main_asuka1() -> None:
    _main("asuka-1")


if __name__ == "__main__":
    main()
