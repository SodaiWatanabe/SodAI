from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import torch
from safetensors.torch import load_file
from sodai_contracts.inference import FinishReason, GenerationJob

from sodai_inference.architectures.absolute_position_gpt import AbsoluteGPT, GPTConfig
from sodai_inference.artifacts import ArtifactManifest, sha256_file, sha256_tree
from sodai_inference.models.hina.decoder import IncrementalTextDecoder
from sodai_inference.models.hina.prompt import HinaPromptBuilder, load_tokenizer


@dataclass(frozen=True, slots=True)
class GenerationStep:
    delta: str
    content: str
    output_tokens: int
    finish_reason: FinishReason | None = None


class HinaEngine:
    model_name = "hina"

    def __init__(
        self,
        *,
        artifact_path: Path,
        manifest: ArtifactManifest,
        model: AbsoluteGPT,
        tokenizer,
        device: torch.device,
    ) -> None:
        self.artifact_path = artifact_path
        self.manifest = manifest
        self._model = model
        self._tokenizer = tokenizer
        self._prompt_builder = HinaPromptBuilder(tokenizer)
        self._device = device
        self._stop_token_ids = {
            tokenizer.eos_token_id,
            tokenizer.convert_tokens_to_ids("<|end_turn|>"),
        }

    @property
    def resolved_model(self) -> str:
        return f"hina@{self.manifest.artifact_id}"

    @classmethod
    def load(cls, artifact_path: Path, device_name: str) -> HinaEngine:
        manifest = ArtifactManifest.load(artifact_path / "manifest.json")
        manifest.validate_hina()
        weights_path = artifact_path / "model.safetensors"
        if sha256_file(weights_path) != manifest.checkpoint_sha256:
            raise ValueError("Hina artifact weights checksum does not match manifest")

        config_path = artifact_path / "model_config.json"
        if sha256_file(config_path) != manifest.model_config_sha256:
            raise ValueError("Hina artifact model config checksum does not match manifest")
        config_value = json.loads(config_path.read_text("utf-8"))
        config = GPTConfig(**config_value)
        if config.block_size != manifest.context_length:
            raise ValueError("Hina model config and manifest context length differ")

        model = AbsoluteGPT(config)
        state = load_file(weights_path, device="cpu")
        missing, unexpected = model.load_state_dict(state, strict=False)
        if set(missing) != {"lm_head.weight"} or unexpected:
            raise ValueError(
                f"Hina state dict is incompatible: missing={missing}, unexpected={unexpected}"
            )
        device = torch.device(device_name)
        model.to(device).eval()
        tokenizer_path = artifact_path / "tokenizer"
        if sha256_tree(tokenizer_path) != manifest.tokenizer_sha256:
            raise ValueError("Hina artifact tokenizer checksum does not match manifest")
        tokenizer = load_tokenizer(str(tokenizer_path))
        actual_token_ids = {
            token: int(tokenizer.convert_tokens_to_ids(token))
            for token in manifest.special_token_ids
        }
        if actual_token_ids != manifest.special_token_ids:
            raise ValueError("Hina special token IDs do not match manifest")
        return cls(
            artifact_path=artifact_path,
            manifest=manifest,
            model=model,
            tokenizer=tokenizer,
            device=device,
        )

    def build_prompt(self, job: GenerationJob) -> list[int]:
        if job.model != self.model_name:
            raise ValueError(f"Hina engine cannot serve model {job.model}")
        if job.artifact_id != self.manifest.artifact_id:
            raise ValueError(f"Hina artifact {job.artifact_id} is not loaded")
        input_budget = self.manifest.context_length - job.options.max_output_tokens
        return self._prompt_builder.encode(job.turns, input_budget)

    def generate(self, prompt_ids: list[int], job: GenerationJob) -> Iterator[GenerationStep]:
        sequence = torch.tensor([prompt_ids], dtype=torch.long, device=self._device)
        decoder = IncrementalTextDecoder(self._tokenizer)
        generator = torch.Generator(device=self._device)
        generator.manual_seed(job.id.int % (2**63 - 1))
        finish_reason = FinishReason.LENGTH

        with torch.inference_mode():
            for output_tokens in range(1, job.options.max_output_tokens + 1):
                logits = self._model(sequence)[:, -1, :] / job.options.temperature
                next_token = torch.multinomial(
                    torch.softmax(logits, dim=-1), num_samples=1, generator=generator
                )
                token_id = int(next_token.item())
                if token_id in self._stop_token_ids:
                    finish_reason = FinishReason.STOP
                    break
                sequence = torch.cat((sequence, next_token), dim=1)
                delta = decoder.push(token_id)
                if delta:
                    yield GenerationStep(delta, decoder.content, output_tokens)

        final_delta = decoder.finish()
        if final_delta:
            yield GenerationStep(final_delta, decoder.content, output_tokens)
        yield GenerationStep("", decoder.content, output_tokens, finish_reason)
