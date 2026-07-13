from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = 3
HINA_RUNTIME_ABI = "hina-absolute-gpt-v1"
HINA_DTYPE = "float32"
HINA_PROMPT_TEMPLATE = "partner-self-v1"
HINA_VOCAB_SIZE = 32_000
HINA_SPECIAL_TOKENS = (
    "<|pad|>",
    "<|unk|>",
    "<|bos|>",
    "<|eos|>",
    "<|self|>",
    "<|partner|>",
    "<|end_turn|>",
    "<|memory|>",
    "<|context|>",
    "<|bot|>",
    "<|latent|>",
    "<|eot|>",
    "<|tool_call|>",
    "<|end_tool_call|>",
    "<|tool_result|>",
)


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    artifact_id: str
    model: str
    architecture: str
    runtime_abi: str
    context_length: int
    dtype: str
    prompt_template: str
    checkpoint_sha256: str
    model_config_sha256: str
    tokenizer_sha256: str
    source_repository: str
    source_model_version: str
    source_checkpoint_stage: str
    source_checkpoint_step: int | None
    source_git_commit: str | None
    special_token_ids: dict[str, int]

    @classmethod
    def load(cls, path: Path) -> ArtifactManifest:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            raise ValueError("unsupported artifact manifest schema")
        source = _object(value, "source")
        special_token_ids = _object(value, "special_token_ids")
        return cls(
            artifact_id=_string(value, "artifact_id"),
            model=_string(value, "model"),
            architecture=_string(value, "architecture"),
            runtime_abi=_string(value, "runtime_abi"),
            context_length=_integer(value, "context_length"),
            dtype=_string(value, "dtype"),
            prompt_template=_string(value, "prompt_template"),
            checkpoint_sha256=_string(value, "checkpoint_sha256"),
            model_config_sha256=_string(value, "model_config_sha256"),
            tokenizer_sha256=_string(value, "tokenizer_sha256"),
            source_repository=_string(source, "repository"),
            source_model_version=_string(source, "model_version"),
            source_checkpoint_stage=_string(source, "checkpoint_stage"),
            source_checkpoint_step=_optional_integer(source, "checkpoint_step"),
            source_git_commit=_optional_string(source, "git_commit"),
            special_token_ids={
                key: _token_id(special_token_ids, key) for key in special_token_ids
            },
        )

    def validate_hina(self) -> None:
        expected = {
            "model": (self.model, "hina"),
            "architecture": (self.architecture, "absolute_position_gpt"),
            "runtime_abi": (self.runtime_abi, HINA_RUNTIME_ABI),
            "context_length": (self.context_length, 512),
            "dtype": (self.dtype, HINA_DTYPE),
            "prompt_template": (self.prompt_template, HINA_PROMPT_TEMPLATE),
            "source_model_version": (self.source_model_version, "v1"),
            "source_checkpoint_stage": (self.source_checkpoint_stage, "sft"),
        }
        mismatches = [name for name, (actual, wanted) in expected.items() if actual != wanted]
        if mismatches:
            raise ValueError(f"artifact is incompatible with Hina runtime: {', '.join(mismatches)}")
        if set(self.special_token_ids) != set(HINA_SPECIAL_TOKENS):
            raise ValueError("artifact does not define the exact Hina special token set")
        token_ids = tuple(self.special_token_ids.values())
        if any(
            isinstance(token_id, bool) or not 0 <= token_id < HINA_VOCAB_SIZE
            for token_id in token_ids
        ):
            raise ValueError("artifact contains a special token ID outside Hina's vocabulary")
        if len(set(token_ids)) != len(token_ids):
            raise ValueError("artifact contains duplicate Hina special token IDs")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path) -> str:
    candidates = sorted(path.rglob("*"))
    symlink = next((candidate for candidate in candidates if candidate.is_symlink()), None)
    if symlink is not None:
        raise ValueError(f"artifact directory cannot contain symlinks: {symlink}")
    files = [candidate for candidate in candidates if candidate.is_file()]
    if not files:
        raise ValueError(f"artifact directory is empty: {path}")
    digest = hashlib.sha256()
    for candidate in files:
        relative = candidate.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        with candidate.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _object(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"manifest field {key} must be an object")
    return item


def _string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"manifest field {key} must be a non-empty string")
    return item


def _integer(value: dict[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"manifest field {key} must be an integer")
    return item


def _optional_integer(value: dict[str, Any], key: str) -> int | None:
    item = value.get(key)
    if item is None:
        return None
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"manifest field {key} must be an integer or null")
    return item


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str):
        raise ValueError(f"manifest field {key} must be a string or null")
    return item


def _token_id(value: dict[str, Any], key: Any) -> int:
    if not isinstance(key, str) or not key:
        raise ValueError("manifest special token names must be non-empty strings")
    token_id = value[key]
    if isinstance(token_id, bool) or not isinstance(token_id, int):
        raise ValueError(f"manifest special token {key} must have an integer ID")
    return token_id
