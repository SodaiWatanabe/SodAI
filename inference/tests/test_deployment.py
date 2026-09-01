import json
import stat

import pytest

from sodai_inference.artifacts import MANIFEST_SCHEMA_VERSION, sha256_file, sha256_tree
from sodai_inference.deployment import (
    activate_deployment,
    activate_hina_artifact,
    resolve_artifact,
    resolve_hina_artifact,
)
from sodai_inference.models.asuka1.profile import ASUKA1_PROFILE
from sodai_inference.models.hina.profile import HINA_PROFILE

ARTIFACT_ID = "0123456789abcdef"


def create_artifact(tmp_path, profile=HINA_PROFILE):
    artifact = tmp_path / profile.model / ARTIFACT_ID
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
                "model": profile.model,
                "architecture": profile.architecture,
                "runtime_abi": profile.runtime_abi,
                "context_length": profile.context_length,
                "dtype": profile.dtype,
                "prompt_template": profile.prompt_template,
                "checkpoint_sha256": sha256_file(weights),
                "model_config_sha256": sha256_file(config),
                "tokenizer_sha256": sha256_tree(tokenizer),
                "source": {
                    "repository": "Building-SLM",
                    "model_version": profile.source_model_version,
                    "checkpoint_stage": profile.source_checkpoint_stage,
                    "checkpoint_step": None,
                    "git_commit": None,
                },
                "special_token_ids": {
                    token: token_id
                    for token_id, token in enumerate(profile.special_tokens)
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


def test_named_deployment_routes_asuka_versions_to_one_runtime(tmp_path) -> None:
    artifact = create_artifact(tmp_path, ASUKA1_PROFILE)

    activated = activate_deployment(
        tmp_path,
        "asuka-1.1",
        "asuka-1",
        ARTIFACT_ID,
    )

    assert activated == artifact
    assert (
        resolve_artifact(
            tmp_path,
            "asuka-1",
            deployment_name="asuka-1.1",
        )
        == artifact
    )
    deployment = json.loads(
        (tmp_path / "deployments" / "asuka-1.1.json").read_text(encoding="utf-8")
    )
    assert deployment == {
        "schema_version": 1,
        "deployment": "asuka-1.1",
        "model": "asuka-1",
        "artifact_id": ARTIFACT_ID,
    }


def test_activation_grants_the_model_group_read_only_access(tmp_path) -> None:
    create_artifact(tmp_path)
    for path in (tmp_path, *tmp_path.rglob("*")):
        path.chmod(0o700 if path.is_dir() else 0o600)

    activate_hina_artifact(tmp_path, ARTIFACT_ID)

    for path in (tmp_path, *tmp_path.rglob("*")):
        mode = path.stat().st_mode
        assert mode & stat.S_IRGRP
        if path.is_dir():
            assert mode & stat.S_IXGRP
        assert mode & stat.S_IWGRP == 0
        assert mode & stat.S_IROTH == 0
        assert mode & stat.S_IWOTH == 0
        assert mode & stat.S_IXOTH == 0


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
