from __future__ import annotations

from dataclasses import dataclass
from re import fullmatch
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InferenceNamespace:
    """Derives every Redis key and consumer group for one inference environment."""

    prefix: str = "sodai:inference"

    def __post_init__(self) -> None:
        if (
            fullmatch(r"[A-Za-z0-9][A-Za-z0-9:_-]{0,127}", self.prefix) is None
            or self.prefix.endswith((":", "-", "_"))
            or "::" in self.prefix
        ):
            raise ValueError("inference namespace contains unsupported characters")

    @property
    def job_stream(self) -> str:
        return f"{self.prefix}:jobs:v2"

    @property
    def event_stream(self) -> str:
        return f"{self.prefix}:events:v2"

    @property
    def projector_group(self) -> str:
        return f"{self._group_prefix}-projector-v2"

    @property
    def worker_group(self) -> str:
        return f"{self._group_prefix}-workers-v2"

    def job_stream_for(self, model: str, artifact_id: str) -> str:
        self._validate_segment(model, "model")
        self._validate_segment(artifact_id, "artifact_id")
        return f"{self.job_stream}:{model}:{artifact_id}"

    def attempt_lock(self, attempt_id: UUID) -> str:
        return f"{self.prefix}:attempt:{attempt_id}"

    def attempt_progress(self, attempt_id: UUID) -> str:
        return f"{self.attempt_lock(attempt_id)}:progress"

    def attempt_cancellation(self, attempt_id: UUID) -> str:
        return f"{self.attempt_lock(attempt_id)}:cancelled"

    def worker_readiness(self, model: str, artifact_id: str) -> str:
        self._validate_segment(model, "model")
        self._validate_segment(artifact_id, "artifact_id")
        return f"{self.prefix}:worker:ready:{model}:{artifact_id}"

    @property
    def key_pattern(self) -> str:
        return f"{self.prefix}:*"

    @property
    def _group_prefix(self) -> str:
        return self.prefix.replace(":", "-")

    @staticmethod
    def _validate_segment(value: str, name: str) -> None:
        if fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is None:
            raise ValueError(f"{name} contains unsupported characters")
