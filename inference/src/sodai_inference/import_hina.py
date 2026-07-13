from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import torch
from safetensors.torch import save_file
from transformers import PreTrainedTokenizerFast

from sodai_inference.architectures.absolute_position_gpt import AbsoluteGPT, GPTConfig
from sodai_inference.artifacts import (
    HINA_DTYPE,
    HINA_PROMPT_TEMPLATE,
    HINA_RUNTIME_ABI,
    HINA_SPECIAL_TOKENS,
    HINA_VOCAB_SIZE,
    MANIFEST_SCHEMA_VERSION,
    ArtifactManifest,
    sha256_file,
    sha256_tree,
)
from sodai_inference.config import Settings
from sodai_inference.models.hina.prompt import SPECIAL_TOKENS

EXPECTED_CONFIG = {
    "vocab_size": 32000,
    "block_size": 512,
    "n_embd": 1024,
    "n_head": 16,
    "n_layer": 18,
    "dropout": 0.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Import the Building-SLM v1 SFT checkpoint as Hina")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
    )
    parser.add_argument("--source-repository", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact_path = import_hina(
        checkpoint=args.checkpoint.resolve(),
        tokenizer_path=args.tokenizer.resolve(),
        output_root=(args.output_root or Settings.from_env().model_root).resolve(),
        source_repository=args.source_repository.resolve() if args.source_repository else None,
    )
    print(f"Hina artifact: {artifact_path}")


def import_hina(
    *,
    checkpoint: Path,
    tokenizer_path: Path,
    output_root: Path,
    source_repository: Path | None,
) -> Path:
    checkpoint_sha256 = sha256_file(checkpoint)
    tokenizer_sha256 = sha256_tree(tokenizer_path)
    artifact_id = hashlib.sha256(
        (
            f"{checkpoint_sha256}:{tokenizer_sha256}:"
            f"{HINA_RUNTIME_ABI}:manifest-{MANIFEST_SCHEMA_VERSION}"
        ).encode()
    ).hexdigest()[:16]
    hina_root = output_root / "hina"
    artifact_path = hina_root / artifact_id

    checkpoint_value = torch.load(checkpoint, map_location="cpu", weights_only=True)
    _validate_checkpoint(checkpoint_value)
    _validate_runtime_state(checkpoint_value["model_state_dict"])
    tokenizer = _load_and_validate_tokenizer(tokenizer_path)
    source_commit = _git_commit(source_repository)

    if not artifact_path.exists():
        hina_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".hina-import-", dir=hina_root) as temporary:
            staging = Path(temporary)
            state = {
                key: value.detach().cpu()
                for key, value in checkpoint_value["model_state_dict"].items()
                if key != "lm_head.weight"
            }
            weights_path = staging / "model.safetensors"
            save_file(state, weights_path, metadata={"format": "pt", "model": "hina"})
            model_config = _normalized_config(checkpoint_value["model_config"])
            model_config_path = staging / "model_config.json"
            model_config_path.write_text(
                json.dumps(model_config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            shutil.copytree(tokenizer_path, staging / "tokenizer")
            manifest = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "artifact_id": artifact_id,
                "model": "hina",
                "architecture": "absolute_position_gpt",
                "runtime_abi": HINA_RUNTIME_ABI,
                "context_length": 512,
                "dtype": HINA_DTYPE,
                "prompt_template": HINA_PROMPT_TEMPLATE,
                "checkpoint_sha256": sha256_file(weights_path),
                "model_config_sha256": sha256_file(model_config_path),
                "source_checkpoint_sha256": checkpoint_sha256,
                "tokenizer_sha256": tokenizer_sha256,
                "source": {
                    "repository": "Building-SLM",
                    "model_version": "v1",
                    "checkpoint_stage": "sft",
                    "checkpoint_step": _optional_int(checkpoint_value.get("step")),
                    "git_commit": source_commit,
                },
                "special_token_ids": {
                    token: int(tokenizer.convert_tokens_to_ids(token))
                    for token in HINA_SPECIAL_TOKENS
                },
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(staging, artifact_path)

    _validate_artifact(
        artifact_path,
        artifact_id=artifact_id,
        source_checkpoint_sha256=checkpoint_sha256,
        tokenizer_sha256=tokenizer_sha256,
    )
    return artifact_path


def _validate_checkpoint(value: Any) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("model_state_dict"), dict):
        raise ValueError("checkpoint does not contain a model_state_dict")
    model_version = value.get("model_version", "v1")
    architecture = value.get("model_architecture", "absolute_position_gpt")
    if model_version != "v1" or architecture != "absolute_position_gpt":
        raise ValueError("checkpoint is not Building-SLM v1 SFT")
    if _normalized_config(value.get("model_config")) != EXPECTED_CONFIG:
        raise ValueError("checkpoint model config does not match Hina")


def _validate_runtime_state(state: dict[str, torch.Tensor]) -> None:
    model = AbsoluteGPT(GPTConfig(**EXPECTED_CONFIG))
    model.load_state_dict(state, strict=True)
    del model


def _normalized_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("checkpoint does not contain model_config")
    return {key: value.get(key, default) for key, default in EXPECTED_CONFIG.items()}


def _load_and_validate_tokenizer(path: Path) -> PreTrainedTokenizerFast:
    tokenizer = PreTrainedTokenizerFast.from_pretrained(
        path,
        bos_token="<|bos|>",
        eos_token="<|eos|>",
        unk_token="<|unk|>",
        pad_token="<|pad|>",
        additional_special_tokens=list(SPECIAL_TOKENS),
    )
    if len(tokenizer) != HINA_VOCAB_SIZE:
        raise ValueError(f"Hina tokenizer must contain exactly {HINA_VOCAB_SIZE} tokens")
    token_ids = [tokenizer.convert_tokens_to_ids(token) for token in HINA_SPECIAL_TOKENS]
    if any(
        not isinstance(token_id, int)
        or not 0 <= token_id < HINA_VOCAB_SIZE
        or tokenizer.convert_ids_to_tokens(token_id) != token
        for token, token_id in zip(HINA_SPECIAL_TOKENS, token_ids, strict=True)
    ):
        raise ValueError("tokenizer is missing an in-vocabulary Hina special token")
    if len(set(token_ids)) != len(token_ids):
        raise ValueError("Hina special token IDs must be unique")
    return tokenizer


def _validate_artifact(
    artifact_path: Path,
    *,
    artifact_id: str,
    source_checkpoint_sha256: str,
    tokenizer_sha256: str,
) -> None:
    manifest = ArtifactManifest.load(artifact_path / "manifest.json")
    manifest.validate_hina()
    if manifest.artifact_id != artifact_id:
        raise ValueError("existing Hina artifact has an unexpected artifact ID")
    if manifest.tokenizer_sha256 != tokenizer_sha256:
        raise ValueError("existing Hina artifact has an unexpected tokenizer")
    value = json.loads((artifact_path / "manifest.json").read_text(encoding="utf-8"))
    if value.get("source_checkpoint_sha256") != source_checkpoint_sha256:
        raise ValueError("existing Hina artifact has an unexpected source checkpoint")
    if sha256_file(artifact_path / "model.safetensors") != manifest.checkpoint_sha256:
        raise ValueError("existing Hina artifact weights are corrupted")
    if sha256_file(artifact_path / "model_config.json") != manifest.model_config_sha256:
        raise ValueError("existing Hina artifact config is corrupted")
    if sha256_tree(artifact_path / "tokenizer") != tokenizer_sha256:
        raise ValueError("existing Hina artifact tokenizer is corrupted")


def _git_commit(repository: Path | None) -> str | None:
    if repository is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


if __name__ == "__main__":
    main()
