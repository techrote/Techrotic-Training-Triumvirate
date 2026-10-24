"""Public experiment CLI exposes deterministic non-GPU control-plane operations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.cli import main
from techrotic_training_triumvirate.experiments.rehearsal import simulation_plan


def test_experiment_validate_and_rehearse_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = simulation_plan(tmp_path / "artifacts")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan.to_object()), encoding="utf-8")
    assert main(["experiments", "validate", str(plan_path)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["valid"] is True
    assert validated["experiment_id"] == plan.experiment_id

    ratings = tmp_path / "ratings.json"
    ratings.write_text(
        json.dumps({"humour": 3, "surprise": 4, "distinctiveness": 5}),
        encoding="utf-8",
    )
    database = tmp_path / "state.sqlite3"
    output = tmp_path / "rehearsal"
    assert (
        main(
            [
                "experiments",
                "--db",
                str(database),
                "rehearse",
                "--output",
                str(output),
                "--review",
                str(ratings),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["state"] == "COMPLETE"
    assert report["qualifies_candidate"] is False

    assert (
        main(
            [
                "experiments",
                "--db",
                str(database),
                "verify",
                report["experiment_id"],
            ]
        )
        == 0
    )
    verified = json.loads(capsys.readouterr().out)
    assert verified["verified"] is True
    assert verified["state"] == "COMPLETE"
    assert verified["qualifies_candidate"] is False


def test_actual_run_registers_preflight_without_launching_gpu_work(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    simulated = simulation_plan(tmp_path / "actual")
    actual = simulated.__class__(
        source_archive_sha256=simulated.source_archive_sha256,
        semantic_commit=simulated.semantic_commit,
        model_identity_sha256=simulated.model_identity_sha256,
        dataset_identity_sha256=simulated.dataset_identity_sha256,
        profile_identity_sha256=simulated.profile_identity_sha256,
        target_gpu_uuid=simulated.target_gpu_uuid,
        gpu_budget_seconds=simulated.gpu_budget_seconds,
        cpu_budget_seconds=simulated.cpu_budget_seconds,
        artifact_root=simulated.artifact_root,
        simulation=False,
    )
    plan_path = tmp_path / "actual-plan.json"
    plan_path.write_text(json.dumps(actual.to_object()), encoding="utf-8")
    database = tmp_path / "actual.sqlite3"
    assert (
        main(
            [
                "experiments",
                "--db",
                str(database),
                "run",
                str(plan_path),
                "--detach",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["state"] == "PREFLIGHT"
    assert status["event_count"] == 1
    assert status["active_reservations"] == []
    assert status["next_action"] == "run_preflight"
