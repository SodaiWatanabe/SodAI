from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

from sodai_contracts.inference import (
    INFERENCE_ATTEMPT_LOCK_SECONDS,
    INFERENCE_JOB_CLAIM_IDLE_MS,
    InferenceNamespace,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class Settings:
    model_root: Path
    redis_url: str
    redis_password: str | None
    device: str
    consumer_name: str
    artifact_id: str | None = None
    inference_namespace: str = "sodai:inference"
    job_claim_idle_ms: int = INFERENCE_JOB_CLAIM_IDLE_MS
    run_lock_seconds: int = INFERENCE_ATTEMPT_LOCK_SECONDS

    @classmethod
    def from_env(cls) -> Settings:
        redis_password = os.getenv("REDIS_PASSWORD") or None
        model_root = Path(os.getenv("SODAI_MODEL_ROOT", REPOSITORY_ROOT / "var" / "models"))
        if not model_root.is_absolute():
            model_root = REPOSITORY_ROOT / model_root
        return cls(
            model_root=model_root.resolve(),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:13204/0"),
            redis_password=redis_password,
            device=os.getenv("HINA_DEVICE", "cuda:0"),
            consumer_name=os.getenv(
                "INFERENCE_CONSUMER_NAME", f"{socket.gethostname()}-{os.getpid()}"
            ),
            artifact_id=os.getenv("HINA_ARTIFACT_ID") or None,
            inference_namespace=os.getenv("INFERENCE_NAMESPACE", "sodai:inference"),
        )

    @property
    def inference_keys(self) -> InferenceNamespace:
        return InferenceNamespace(self.inference_namespace)
