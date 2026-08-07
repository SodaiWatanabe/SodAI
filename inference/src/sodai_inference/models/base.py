from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from sodai_contracts.inference import FinishReason, GenerationJob, GenerationPhase

from sodai_inference.artifacts import ArtifactManifest


@dataclass(frozen=True, slots=True)
class GenerationStep:
    phase: GenerationPhase
    delta: str
    content: str
    output_tokens: int
    phase_tokens: int
    finish_reason: FinishReason | None = None


class InferenceEngine(Protocol):
    model_name: str
    manifest: ArtifactManifest
    initial_phase: GenerationPhase

    @property
    def resolved_model(self) -> str: ...

    def build_prompt(self, job: GenerationJob) -> list[int]: ...

    def generate(
        self, prompt_ids: list[int], job: GenerationJob
    ) -> Iterator[GenerationStep]: ...
