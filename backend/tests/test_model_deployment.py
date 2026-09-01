import json

import pytest

from app.services.inference import ModelDeploymentError, ModelDeploymentRegistry


def test_resolves_immutable_hina_artifact(tmp_path) -> None:
    deployment = tmp_path / "hina" / "deployment.json"
    deployment.parent.mkdir()
    artifact = deployment.parent / "797fb28e6eb46da6" / "manifest.json"
    artifact.parent.mkdir()
    artifact.write_text(
        json.dumps({"model": "hina", "artifact_id": "797fb28e6eb46da6"}),
        encoding="utf-8",
    )
    deployment.write_text(
        json.dumps({"model": "hina", "artifact_id": "797fb28e6eb46da6"}),
        encoding="utf-8",
    )

    resolved = ModelDeploymentRegistry(tmp_path).resolve("hina")

    assert resolved.resolved_model == "hina@797fb28e6eb46da6"


def test_named_deployment_can_share_the_asuka_runtime(tmp_path) -> None:
    artifact_id = "cf34c76742725e86"
    artifact = tmp_path / "asuka-1" / artifact_id / "manifest.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps({"model": "asuka-1", "artifact_id": artifact_id}),
        encoding="utf-8",
    )
    deployment = tmp_path / "deployments" / "asuka-1.1.json"
    deployment.parent.mkdir()
    deployment.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "deployment": "asuka-1.1",
                "model": "asuka-1",
                "artifact_id": artifact_id,
            }
        ),
        encoding="utf-8",
    )

    resolved = ModelDeploymentRegistry(tmp_path).resolve("asuka-1.1")

    assert resolved.deployment_name == "asuka-1.1"
    assert resolved.model == "asuka-1"
    assert resolved.resolved_model == f"asuka-1@{artifact_id}"


def test_rejects_mismatched_deployment(tmp_path) -> None:
    deployment = tmp_path / "hina" / "deployment.json"
    deployment.parent.mkdir()
    deployment.write_text(
        json.dumps({"model": "asuka-1", "artifact_id": "wrong"}),
        encoding="utf-8",
    )

    with pytest.raises(ModelDeploymentError):
        ModelDeploymentRegistry(tmp_path).resolve("hina")
