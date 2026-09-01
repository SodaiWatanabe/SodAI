from __future__ import annotations

import asyncio

from redis.asyncio import Redis

from sodai_inference.artifacts import ArtifactManifest
from sodai_inference.config import Settings
from sodai_inference.deployment import resolve_artifact


async def check() -> None:
    settings = Settings.from_env()
    artifact_path = resolve_artifact(
        settings.model_root,
        settings.model_name,
        settings.artifact_id,
        deployment_name=settings.deployment_name,
    )
    artifact_id = ArtifactManifest.load(artifact_path / "manifest.json").artifact_id
    redis = Redis.from_url(
        settings.redis_url,
        password=settings.redis_password,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        readiness_key = settings.inference_keys.worker_readiness(
            settings.model_name,
            artifact_id,
        )
        if await redis.get(readiness_key) is None:
            raise RuntimeError("inference worker readiness lease is absent")
    finally:
        await redis.aclose()


def main() -> None:
    asyncio.run(check())


if __name__ == "__main__":
    main()
