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

from sodai_inference.architectures.rope_gpt import GPTConfig, RoPEGPT
from sodai_inference.artifacts import (
    MANIFEST_SCHEMA_VERSION,
    ArtifactManifest,
    sha256_file,
    sha256_tree,
)
from sodai_inference.config import Settings
from sodai_inference.models.asuka1.profile import ASUKA1_PROFILE
from sodai_inference.tokenization import load_chat_tokenizer, special_token_ids

EXPECTED_CONFIG = {
    "vocab_size": 32_000,
    "block_size": 512,
    "n_embd": 1_024,
    "n_head": 16,
    "n_layer": 36,
    "dropout": 0.0,
    "ffn_multiple_of": 256,
    "ffn_hidden_size": 3_584,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Import the Building-SLM v2 SFT checkpoint as Asuka 1")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--source-repository", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact_path = import_asuka1(
        checkpoint=args.checkpoint.resolve(),
        tokenizer_path=args.tokenizer.resolve(),
        output_root=(args.output_root or Settings.from_env().model_root).resolve(),
        source_repository=args.source_repository.resolve() if args.source_repository else None,
    )
    print(f"Asuka 1 artifact: {artifact_path}")


def import_asuka1(
    *,
    checkpoint: Path,
    tokenizer_path: Path,
    output_root: Path,
    source_repository: Path | None,
) -> Path:
    source_checkpoint_sha256 = sha256_file(checkpoint)
    tokenizer_sha256 = sha256_tree(tokenizer_path)
    artifact_id = hashlib.sha256(
        (
            f"{source_checkpoint_sha256}:{tokenizer_sha256}:"
            f"{ASUKA1_PROFILE.runtime_abi}:manifest-{MANIFEST_SCHEMA_VERSION}"
        ).encode()
    ).hexdigest()[:16]
    model_root = output_root / ASUKA1_PROFILE.model
    artifact_path = model_root / artifact_id

    checkpoint_value = torch.load(
        checkpoint,
        map_location="cpu",
        weights_only=True,
        mmap=True,
    )
    _validate_checkpoint(checkpoint_value)
    _validate_runtime_state(checkpoint_value["model_state_dict"])
    tokenizer = _load_and_validate_tokenizer(tokenizer_path)
    source_commit = _git_commit(source_repository)

    if not artifact_path.exists():
        model_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".asuka1-import-", dir=model_root) as temporary:
            staging = Path(temporary)
            state = {
                key: tensor.detach().cpu().to(dtype=torch.float16).contiguous()
                for key, tensor in checkpoint_value["model_state_dict"].items()
                if key != "lm_head.weight"
            }
            weights_path = staging / "model.safetensors"
            save_file(state, weights_path, metadata={"format": "pt", "model": "asuka-1"})
            del state

            model_config = _normalized_config(checkpoint_value["model_config"])
            config_path = staging / "model_config.json"
            config_path.write_text(
                json.dumps(model_config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            shutil.copytree(tokenizer_path, staging / "tokenizer")
            manifest = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "artifact_id": artifact_id,
                "model": ASUKA1_PROFILE.model,
                "architecture": ASUKA1_PROFILE.architecture,
                "runtime_abi": ASUKA1_PROFILE.runtime_abi,
                "context_length": ASUKA1_PROFILE.context_length,
                "dtype": ASUKA1_PROFILE.dtype,
                "prompt_template": ASUKA1_PROFILE.prompt_template,
                "checkpoint_sha256": sha256_file(weights_path),
                "model_config_sha256": sha256_file(config_path),
                "source_checkpoint_sha256": source_checkpoint_sha256,
                "tokenizer_sha256": tokenizer_sha256,
                "source": {
                    "repository": (
                        source_repository.name if source_repository is not None else "Building-SLM"
                    ),
                    "model_version": ASUKA1_PROFILE.source_model_version,
                    "checkpoint_stage": ASUKA1_PROFILE.source_checkpoint_stage,
                    "checkpoint_step": _optional_int(checkpoint_value.get("step")),
                    "git_commit": source_commit,
                },
                "special_token_ids": special_token_ids(tokenizer),
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(staging, artifact_path)

    _validate_artifact(
        artifact_path,
        artifact_id=artifact_id,
        source_checkpoint_sha256=source_checkpoint_sha256,
        tokenizer_sha256=tokenizer_sha256,
    )
    return artifact_path


def _validate_checkpoint(value: Any) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("model_state_dict"), dict):
        raise ValueError("checkpoint does not contain a model_state_dict")
    if value.get("model_version") != "v2" or value.get("model_architecture") != "rope_gpt":
        raise ValueError("checkpoint is not Building-SLM v2 SFT")
    if _normalized_config(value.get("model_config")) != EXPECTED_CONFIG:
        raise ValueError("checkpoint model config does not match Asuka 1")


def _validate_runtime_state(state: dict[str, torch.Tensor]) -> None:
    with torch.device("meta"):
        expected = RoPEGPT(GPTConfig(**EXPECTED_CONFIG)).state_dict()
    if set(state) != set(expected):
        missing = sorted(set(expected) - set(state))
        unexpected = sorted(set(state) - set(expected))
        raise ValueError(
            f"Asuka 1 state dict keys are incompatible: missing={missing}, "
            f"unexpected={unexpected}"
        )
    mismatched = [
        key for key in expected if tuple(state[key].shape) != tuple(expected[key].shape)
    ]
    if mismatched:
        raise ValueError(f"Asuka 1 state dict shapes are incompatible: {mismatched}")


def _normalized_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("checkpoint does not contain model_config")
    return {key: value.get(key, default) for key, default in EXPECTED_CONFIG.items()}


def _load_and_validate_tokenizer(path: Path) -> PreTrainedTokenizerFast:
    tokenizer = load_chat_tokenizer(str(path))
    if len(tokenizer) != ASUKA1_PROFILE.vocab_size:
        raise ValueError(
            f"Asuka 1 tokenizer must contain exactly {ASUKA1_PROFILE.vocab_size} tokens"
        )
    token_ids = [
        tokenizer.convert_tokens_to_ids(token) for token in ASUKA1_PROFILE.special_tokens
    ]
    if any(
        not isinstance(token_id, int)
        or not 0 <= token_id < ASUKA1_PROFILE.vocab_size
        or tokenizer.convert_ids_to_tokens(token_id) != token
        for token, token_id in zip(ASUKA1_PROFILE.special_tokens, token_ids, strict=True)
    ):
        raise ValueError("tokenizer is missing an in-vocabulary Asuka 1 special token")
    if len(set(token_ids)) != len(token_ids):
        raise ValueError("Asuka 1 special token IDs must be unique")
    return tokenizer


def _validate_artifact(
    artifact_path: Path,
    *,
    artifact_id: str,
    source_checkpoint_sha256: str,
    tokenizer_sha256: str,
) -> None:
    manifest = ArtifactManifest.load(artifact_path / "manifest.json")
    manifest.validate(ASUKA1_PROFILE)
    if manifest.artifact_id != artifact_id:
        raise ValueError("existing Asuka 1 artifact has an unexpected artifact ID")
    value = json.loads((artifact_path / "manifest.json").read_text(encoding="utf-8"))
    if value.get("source_checkpoint_sha256") != source_checkpoint_sha256:
        raise ValueError("existing Asuka 1 artifact has an unexpected source checkpoint")
    if manifest.tokenizer_sha256 != tokenizer_sha256:
        raise ValueError("existing Asuka 1 artifact has an unexpected tokenizer")
    if sha256_file(artifact_path / "model.safetensors") != manifest.checkpoint_sha256:
        raise ValueError("existing Asuka 1 artifact weights are corrupted")
    if sha256_file(artifact_path / "model_config.json") != manifest.model_config_sha256:
        raise ValueError("existing Asuka 1 artifact config is corrupted")
    if sha256_tree(artifact_path / "tokenizer") != tokenizer_sha256:
        raise ValueError("existing Asuka 1 artifact tokenizer is corrupted")


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
