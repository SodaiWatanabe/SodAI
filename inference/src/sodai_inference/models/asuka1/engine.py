from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import torch
from safetensors.torch import load_file
from sodai_contracts.inference import FinishReason, GenerationJob, GenerationPhase

from sodai_inference.architectures.rope_gpt import GPTConfig, RoPEGPT
from sodai_inference.artifacts import ArtifactManifest, sha256_file, sha256_tree
from sodai_inference.models.asuka1.profile import ASUKA1_PROFILE
from sodai_inference.models.asuka1.prompt import Asuka1PromptBuilder, load_tokenizer
from sodai_inference.models.base import GenerationStep
from sodai_inference.models.decoder import IncrementalTextDecoder

TOP_P = 0.90
REPETITION_PENALTY = 1.10


class Asuka1Engine:
    model_name = "asuka-1"
    initial_phase = GenerationPhase.THINKING

    def __init__(
        self,
        *,
        artifact_path: Path,
        manifest: ArtifactManifest,
        model: RoPEGPT,
        tokenizer,
        device: torch.device,
    ) -> None:
        self.artifact_path = artifact_path
        self.manifest = manifest
        self._model = model
        self._tokenizer = tokenizer
        self._prompt_builder = Asuka1PromptBuilder(tokenizer)
        self._device = device
        self._eot_id = tokenizer.convert_tokens_to_ids("<|eot|>")
        self._stop_token_ids = {
            tokenizer.eos_token_id,
            tokenizer.convert_tokens_to_ids("<|end_turn|>"),
        }

    @property
    def resolved_model(self) -> str:
        return f"{self.model_name}@{self.manifest.artifact_id}"

    @classmethod
    def load(cls, artifact_path: Path, device_name: str) -> Asuka1Engine:
        manifest = ArtifactManifest.load(artifact_path / "manifest.json")
        manifest.validate(ASUKA1_PROFILE)
        weights_path = artifact_path / "model.safetensors"
        if sha256_file(weights_path) != manifest.checkpoint_sha256:
            raise ValueError("Asuka 1 artifact weights checksum does not match manifest")
        config_path = artifact_path / "model_config.json"
        if sha256_file(config_path) != manifest.model_config_sha256:
            raise ValueError("Asuka 1 artifact config checksum does not match manifest")
        config = GPTConfig(**json.loads(config_path.read_text(encoding="utf-8")))
        if config.block_size != manifest.context_length:
            raise ValueError("Asuka 1 model config and manifest context length differ")

        model = RoPEGPT(config)
        state = load_file(weights_path, device="cpu")
        missing, unexpected = model.load_state_dict(state, strict=False)
        if set(missing) != {"lm_head.weight"} or unexpected:
            raise ValueError(
                f"Asuka 1 state dict is incompatible: missing={missing}, "
                f"unexpected={unexpected}"
            )
        device = torch.device(device_name)
        model.to(device=device, dtype=torch.float16).eval()

        tokenizer_path = artifact_path / "tokenizer"
        if sha256_tree(tokenizer_path) != manifest.tokenizer_sha256:
            raise ValueError("Asuka 1 artifact tokenizer checksum does not match manifest")
        tokenizer = load_tokenizer(str(tokenizer_path))
        actual_token_ids = {
            token: int(tokenizer.convert_tokens_to_ids(token))
            for token in manifest.special_token_ids
        }
        if actual_token_ids != manifest.special_token_ids:
            raise ValueError("Asuka 1 special token IDs do not match manifest")
        return cls(
            artifact_path=artifact_path,
            manifest=manifest,
            model=model,
            tokenizer=tokenizer,
            device=device,
        )

    def build_prompt(self, job: GenerationJob) -> list[int]:
        if job.model != self.model_name:
            raise ValueError(f"Asuka 1 engine cannot serve model {job.model}")
        if job.artifact_id != self.manifest.artifact_id:
            raise ValueError(f"Asuka 1 artifact {job.artifact_id} is not loaded")
        input_budget = self.manifest.context_length - job.options.max_output_tokens
        return self._prompt_builder.encode(job.turns, input_budget)

    def generate(self, prompt_ids: list[int], job: GenerationJob) -> Iterator[GenerationStep]:
        sequence = torch.tensor([prompt_ids], dtype=torch.long, device=self._device)
        thinking_decoder = IncrementalTextDecoder(self._tokenizer)
        answer_decoder = IncrementalTextDecoder(self._tokenizer)
        generator = torch.Generator(device=self._device)
        generator.manual_seed(job.id.int % (2**63 - 1))
        generated_ids: list[int] = []
        answer_started = False
        finish_reason = FinishReason.LENGTH
        output_tokens = 0
        thinking_tokens = 0
        answer_tokens = 0

        with torch.inference_mode():
            logits, _, cache = self._model(sequence, use_cache=True)
            for output_tokens in range(1, job.options.max_output_tokens + 1):
                next_token = self._sample(
                    logits[:, -1, :],
                    generated_ids,
                    temperature=job.options.temperature,
                    generator=generator,
                )
                token_id = int(next_token.item())
                generated_ids.append(token_id)

                if token_id == self._eot_id:
                    if not answer_started:
                        final_thinking_delta = thinking_decoder.finish()
                        yield GenerationStep(
                            GenerationPhase.THINKING,
                            final_thinking_delta,
                            thinking_decoder.content,
                            output_tokens,
                            thinking_tokens,
                        )
                        answer_started = True
                        yield GenerationStep(
                            GenerationPhase.ANSWERING,
                            "",
                            answer_decoder.content,
                            output_tokens,
                            answer_tokens,
                        )
                elif token_id in self._stop_token_ids:
                    if not answer_started:
                        raise ValueError("Asuka 1 stopped before the <|eot|> boundary")
                    finish_reason = FinishReason.STOP
                    break
                elif answer_started:
                    answer_tokens += 1
                    delta = answer_decoder.push(token_id)
                    if delta:
                        yield GenerationStep(
                            GenerationPhase.ANSWERING,
                            delta,
                            answer_decoder.content,
                            output_tokens,
                            answer_tokens,
                        )
                else:
                    thinking_tokens += 1
                    delta = thinking_decoder.push(token_id)
                    if delta:
                        yield GenerationStep(
                            GenerationPhase.THINKING,
                            delta,
                            thinking_decoder.content,
                            output_tokens,
                            thinking_tokens,
                        )

                if output_tokens < job.options.max_output_tokens:
                    logits, _, cache = self._model(
                        next_token,
                        past_key_values=cache,
                        use_cache=True,
                    )

        if not answer_started:
            raise ValueError("Asuka 1 did not produce the <|eot|> boundary")
        final_delta = answer_decoder.finish()
        if final_delta:
            yield GenerationStep(
                GenerationPhase.ANSWERING,
                final_delta,
                answer_decoder.content,
                output_tokens,
                answer_tokens,
            )
        yield GenerationStep(
            GenerationPhase.ANSWERING,
            "",
            answer_decoder.content,
            output_tokens,
            answer_tokens,
            finish_reason,
        )

    @staticmethod
    def _sample(
        logits: torch.Tensor,
        generated_ids: list[int],
        *,
        temperature: float,
        generator: torch.Generator,
    ) -> torch.Tensor:
        logits = logits.float()
        if generated_ids:
            token_ids = torch.tensor(
                sorted(set(generated_ids)),
                dtype=torch.long,
                device=logits.device,
            )
            selected = logits.index_select(-1, token_ids)
            selected = torch.where(
                selected < 0,
                selected * REPETITION_PENALTY,
                selected / REPETITION_PENALTY,
            )
            logits = logits.scatter(-1, token_ids.unsqueeze(0), selected)

        logits = logits / temperature
        sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
        cumulative = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
        sorted_remove = cumulative > TOP_P
        sorted_remove[..., 1:] = sorted_remove[..., :-1].clone()
        sorted_remove[..., 0] = False
        remove = torch.zeros_like(sorted_remove).scatter(-1, sorted_indices, sorted_remove)
        probabilities = torch.softmax(logits.masked_fill(remove, float("-inf")), dim=-1)
        return torch.multinomial(probabilities, 1, generator=generator)
