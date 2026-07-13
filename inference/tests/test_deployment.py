import json

import pytest

from sodai_inference.artifacts import (
    HINA_RUNTIME_ABI,
    HINA_SPECIAL_TOKENS,
    MANIFEST_SCHEMA_VERSION,
    sha256_file,
    sha256_tree,
)
from sodai_inference.deployment import activate_hina_artifact, resolve_hina_artifact

ARTIFACT_ID = "0123456789abcdef"


def create_artifact(tmp_path):
    artifact = tmp_path / "hina" / ARTIFACT_ID
    tokenizer = artifact / "tokenizer"
    tokenizer.mkdir(parents=True)
    weights = artifact / "model.safetensors"
    config = artifact / "model_config.json"
    tokenizer_json = tokenizer / "tokenizer.json"
    tokenizer_config = tokenizer / "tokenizer_config.json"
    weights.write_bytes(b"weights")
    config.write_text("{}\n", encoding="utf-8")
    tokenizer_json.write_text("{}\n", encoding="utf-8")
    tokenizer_config.write_text("{}\n", encoding="utf-8")
    (artifact / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "artifact_id": ARTIFACT_ID,
                "model": "hina",
                "architecture": "absolute_position_gpt",
                "runtime_abi": HINA_RUNTIME_ABI,
                "context_length": 512,
                "dtype": "float32",
                "prompt_template": "partner-self-v1",
                "checkpoint_sha256": sha256_file(weights),
                "model_config_sha256": sha256_file(config),
                "tokenizer_sha256": sha256_tree(tokenizer),
                "source": {
                    "repository": "Building-SLM",
                    "model_version": "v1",
                    "checkpoint_stage": "sft",
                    "checkpoint_step": None,
                    "git_commit": None,
                },
                "special_token_ids": {
                    token: token_id for token_id, token in enumerate(HINA_SPECIAL_TOKENS)
                },
            }
        ),
        encoding="utf-8",
    )
    return artifact


def test_activation_validates_then_atomically_promotes_artifact(tmp_path) -> None:
    artifact = create_artifact(tmp_path)

    activated = activate_hina_artifact(tmp_path, ARTIFACT_ID)

    assert activated == artifact
    assert resolve_hina_artifact(tmp_path) == artifact


def test_activation_rejects_corrupted_artifact(tmp_path) -> None:
    artifact = create_artifact(tmp_path)
    (artifact / "model_config.json").write_text('{"tampered": true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="config is corrupted"):
        activate_hina_artifact(tmp_path, ARTIFACT_ID)


def test_activation_hashes_the_entire_tokenizer_bundle(tmp_path) -> None:
    artifact = create_artifact(tmp_path)
    (artifact / "tokenizer" / "tokenizer_config.json").write_text(
        '{"tampered": true}\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="tokenizer is corrupted"):
        activate_hina_artifact(tmp_path, ARTIFACT_ID)


def test_activation_rejects_an_incomplete_runtime_contract(tmp_path) -> None:
    artifact = create_artifact(tmp_path)
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["special_token_ids"].pop("<|partner|>")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="special token set"):
        activate_hina_artifact(tmp_path, ARTIFACT_ID)


def test_artifact_id_cannot_escape_the_model_root(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid artifact_id"):
        resolve_hina_artifact(tmp_path, "../../outside")
