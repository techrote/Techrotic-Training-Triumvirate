"""TTT-018 verified TRAINED-boundary pause and restart-safety contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.cli import main
from techrotic_training_triumvirate.experiments import (
    EventKind,
    ExperimentContractError,
    ExperimentPlan,
    ExperimentState,
    ExperimentStore,
    ExperimentStoreError,
    VerifiedEvent,
)


def _plan(root: Path) -> ExperimentPlan:
    return ExperimentPlan(
        allocation_id="pause-test",
        created_at="2026-10-26T00:00:00Z",
        source_archive_sha256="1" * 64,
        semantic_commit="2" * 40,
        model_id="model",
        model_sha256="3" * 64,
        tokenizer_sha256="4" * 64,
        dataset_sha256="5" * 64,
        config_sha256="6" * 64,
        gpu_uuid="GPU-22222222-2222-2222-2222-222222222222",
        gpu_hours=1.0,
        artifact_root=str(root),
        candidate_ids=("candidate",),
    )


def _event(kind: EventKind, n: int) -> VerifiedEvent:
    return VerifiedEvent(
        event_id=f"pause-event-{n}",
        kind=kind,
        timestamp=f"2026-10-26T00:00:{n:02d}Z",
        payload={},
    )


def _training(store: ExperimentStore, plan: ExperimentPlan) -> None:
    store.create_plan(plan)
    store.append_event(plan.experiment_id, _event(EventKind.PLAN_VALIDATED, 1))
    store.append_event(plan.experiment_id, _event(EventKind.PREFLIGHT_PASSED, 2))
    store.append_event(plan.experiment_id, _event(EventKind.WORKER_LAUNCHED, 3))


def test_pause_fences_launches_until_training_reconciled_and_survives_restart(
    tmp_path: Path,
) -> None:
    db = tmp_path / "experiment.sqlite"
    plan = _plan(tmp_path)
    attempt = plan.attempt_id("training", ordinal=1, launch_nonce="n1")
    with ExperimentStore(db) as store:
        _training(store, plan)
        store.reserve_budget(plan.experiment_id, attempt, 0.4)
        store.acquire_device_lease(
            plan.experiment_id, attempt, acquired_at="2026-10-26T00:00:03Z"
        )
        pause = _event(EventKind.PAUSE_REQUESTED, 4)
        assert store.append_event(plan.experiment_id, pause) is ExperimentState.PAUSING
        assert store.append_event(plan.experiment_id, pause) is ExperimentState.PAUSING
        with pytest.raises(ExperimentContractError, match="invalid"):
            store.append_event(
                plan.experiment_id, _event(EventKind.DEVELOPMENT_STARTED, 5)
            )
        other = plan.attempt_id("training", ordinal=2, launch_nonce="n2")
        with pytest.raises(ExperimentStoreError, match="pause fence"):
            store.reserve_budget(plan.experiment_id, other, 0.1)
        with pytest.raises(ExperimentStoreError, match="pause fence"):
            store.acquire_device_lease(
                plan.experiment_id, attempt, acquired_at="2026-10-26T00:00:05Z"
            )
        assert (
            store.append_event(
                plan.experiment_id, _event(EventKind.TRAINING_VERIFIED, 6)
            )
            is ExperimentState.PAUSING
        )
        with pytest.raises(ExperimentStoreError, match="active GPU lease"):
            store.append_event(plan.experiment_id, _event(EventKind.PAUSE_CONFIRMED, 7))
        store.release_device_lease(plan.experiment_id, attempt)
        with pytest.raises(ExperimentStoreError, match="reconciled budget"):
            store.append_event(plan.experiment_id, _event(EventKind.PAUSE_CONFIRMED, 7))
        store.reconcile_budget(
            plan.experiment_id, attempt, actual_hours=0.2, lifetime_established=True
        )
        assert (
            store.append_event(plan.experiment_id, _event(EventKind.PAUSE_CONFIRMED, 7))
            is ExperimentState.PAUSED
        )
    with ExperimentStore(db) as store:
        state, hashes = store.replay(plan.experiment_id)
        assert state is ExperimentState.PAUSED
        assert len(hashes) == 6
        assert store.budget_snapshot(plan.experiment_id)["committed_gpu_hours"] == 0.2
        with pytest.raises(ExperimentContractError, match="invalid"):
            store.append_event(
                plan.experiment_id, _event(EventKind.DEVELOPMENT_STARTED, 8)
            )
        with pytest.raises(ExperimentStoreError, match="pause fence"):
            store.reserve_budget(plan.experiment_id, other, 0.1)
        assert (
            store.append_event(
                plan.experiment_id, _event(EventKind.RESUME_REQUESTED, 9)
            )
            is ExperimentState.TRAINED
        )
        assert (
            store.append_event(
                plan.experiment_id, _event(EventKind.RESUME_REQUESTED, 9)
            )
            is ExperimentState.TRAINED
        )
        assert (
            store.append_event(
                plan.experiment_id, _event(EventKind.DEVELOPMENT_STARTED, 10)
            )
            is ExperimentState.DEVELOPMENT
        )
        assert store.budget_snapshot(plan.experiment_id)["committed_gpu_hours"] == 0.2


def test_pause_requires_actual_training_verification(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    with ExperimentStore(tmp_path / "missing.sqlite") as store:
        _training(store, plan)
        store.append_event(plan.experiment_id, _event(EventKind.PAUSE_REQUESTED, 4))
        with pytest.raises(ExperimentStoreError, match="verified TRAINED"):
            store.append_event(plan.experiment_id, _event(EventKind.PAUSE_CONFIRMED, 5))
        assert store.state(plan.experiment_id) is ExperimentState.PAUSING


def test_pause_waits_for_registered_worker_completion(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    attempt = plan.attempt_id("training", ordinal=1, launch_nonce="n1")
    identity = {
        "launch_nonce": "n1",
        "source_hash": "a" * 64,
        "config_hash": "b" * 64,
        "spec_hash": "c" * 64,
        "pid": 1234,
        "creation_token": "example",
    }
    with ExperimentStore(tmp_path / "worker.sqlite") as store:
        _training(store, plan)
        store.reserve_budget(plan.experiment_id, attempt, 0.1)
        store.record_worker(
            plan.experiment_id, attempt, identity=identity, cancel_path="cancel.json"
        )
        store.append_event(plan.experiment_id, _event(EventKind.TRAINING_VERIFIED, 4))
        store.reconcile_budget(
            plan.experiment_id, attempt, actual_hours=0.05, lifetime_established=True
        )
        store.append_event(plan.experiment_id, _event(EventKind.PAUSE_REQUESTED, 5))
        with pytest.raises(ExperimentStoreError, match="worker-host completion"):
            store.append_event(plan.experiment_id, _event(EventKind.PAUSE_CONFIRMED, 6))
        with pytest.raises(ExperimentStoreError, match="pause fence"):
            store.record_worker(
                plan.experiment_id,
                "new-attempt",
                identity=identity,
                cancel_path="cancel.json",
            )
        marker = tmp_path / attempt / "host-complete.json"
        marker.parent.mkdir()
        complete = {
            "schema": "ttt.worker_host_completion",
            "schema_version": 1,
            "attempt_id": attempt,
            "launch_nonce": "wrong",
            "source_hash": "a" * 64,
            "config_hash": "b" * 64,
            "spec_hash": "c" * 64,
            "reason": "exited",
            "returncode": 0,
            "admission_eligible": False,
        }
        marker.write_text(json.dumps(complete), encoding="utf-8")
        with pytest.raises(ExperimentStoreError, match="identity differs"):
            store.record_worker_completion(plan.experiment_id, attempt)
        complete["launch_nonce"] = "n1"
        complete["returncode"] = 124
        marker.write_text(json.dumps(complete), encoding="utf-8")
        with pytest.raises(ExperimentStoreError, match="did not complete"):
            store.record_worker_completion(plan.experiment_id, attempt)
        complete["returncode"] = 0
        marker.write_text(json.dumps(complete), encoding="utf-8")
        store.record_worker_completion(plan.experiment_id, attempt)
        assert (
            store.append_event(plan.experiment_id, _event(EventKind.PAUSE_CONFIRMED, 6))
            is ExperimentState.PAUSED
        )


def test_pause_from_trained_and_cli_unpause_are_non_launching(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "cli.sqlite"
    plan = _plan(tmp_path)
    with ExperimentStore(db) as store:
        _training(store, plan)
        store.append_event(plan.experiment_id, _event(EventKind.TRAINING_VERIFIED, 4))
    assert (
        main(
            [
                "experiments",
                "pause",
                plan.experiment_id,
                "--db",
                str(db),
                "--reason",
                "owner request",
                "--timestamp",
                "2026-10-26T00:01:00Z",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["downstream_fenced"] is True
    assert (
        main(
            [
                "experiments",
                "pause-confirm",
                plan.experiment_id,
                "--db",
                str(db),
                "--timestamp",
                "2026-10-26T00:02:00Z",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["state"] == "PAUSED"
    assert main(["experiments", "resume", plan.experiment_id, "--db", str(db)]) == 0
    assert json.loads(capsys.readouterr().out)["relaunched"] is False
    assert (
        main(
            [
                "experiments",
                "unpause",
                plan.experiment_id,
                "--db",
                str(db),
                "--reason",
                "resume evaluation",
                "--timestamp",
                "2026-10-26T00:03:00Z",
            ]
        )
        == 0
    )
    response = json.loads(capsys.readouterr().out)
    assert response["state"] == "TRAINED"
    assert response["relaunched"] is False
