"""Deterministic orchestration, restart, budget, artifact, and rehearsal tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.experiments import (
    ArtifactVerificationError,
    BudgetError,
    EvidenceClass,
    EvidenceError,
    ExperimentPlan,
    ExperimentState,
    ExperimentStore,
    verify_completion_marker,
    write_completion_marker,
)
from techrotic_training_triumvirate.experiments.adapters import (
    verify_resumable_checkpoint,
)
from techrotic_training_triumvirate.experiments.rehearsal import (
    TITAN_UUID,
    run_rehearsal,
)
from techrotic_training_triumvirate.schemas import canonical_json
from techrotic_training_triumvirate.training import (
    DatasetIdentity,
    TrainingMix,
    load_training_config,
    resolve_model_binding,
)
from techrotic_training_triumvirate.training.campaign_integrity import (
    CampaignIntegrityError,
    expected_training_identity,
)


def _plan(root: Path, *, simulation: bool = False) -> ExperimentPlan:
    return ExperimentPlan(
        source_archive_sha256="1" * 64,
        semantic_commit="2" * 40,
        model_identity_sha256="3" * 64,
        dataset_identity_sha256="4" * 64,
        profile_identity_sha256="5" * 64,
        target_gpu_uuid=TITAN_UUID,
        gpu_budget_seconds=120,
        cpu_budget_seconds=60,
        artifact_root=str(root),
        simulation=simulation,
    )


def test_plan_identity_is_content_derived_and_immutable(tmp_path: Path) -> None:
    first = _plan(tmp_path)
    assert first.experiment_id == _plan(tmp_path).experiment_id
    changed = ExperimentPlan(
        source_archive_sha256=first.source_archive_sha256,
        semantic_commit=first.semantic_commit,
        model_identity_sha256=first.model_identity_sha256,
        dataset_identity_sha256=first.dataset_identity_sha256,
        profile_identity_sha256=first.profile_identity_sha256,
        target_gpu_uuid=first.target_gpu_uuid,
        gpu_budget_seconds=121,
        cpu_budget_seconds=first.cpu_budget_seconds,
        artifact_root=first.artifact_root,
        simulation=first.simulation,
    )
    assert changed.experiment_id != first.experiment_id


def test_event_redelivery_and_restart_replay_are_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "state.sqlite3"
    plan = _plan(tmp_path)
    with ExperimentStore(database) as store:
        experiment_id = store.create_experiment(plan, timestamp_ns=1)
        event = store.append_event(
            experiment_id,
            "PLAN_VALIDATED",
            {"fixture": True},
            timestamp_ns=2,
            idempotency_key="same",
        )
        duplicate = store.append_event(
            experiment_id,
            "PLAN_VALIDATED",
            {"fixture": True},
            timestamp_ns=2,
            idempotency_key="same",
        )
        assert duplicate == event
        assert store.state(experiment_id) == ExperimentState.PREFLIGHT
    with ExperimentStore(database) as reopened:
        assert reopened.replay(experiment_id) == ExperimentState.PREFLIGHT
        assert reopened.events(experiment_id) == (event,)


def test_budget_reservation_survives_restart_and_unknown_exit_charges_cap(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite3"
    plan = _plan(tmp_path)
    with ExperimentStore(database) as store:
        experiment_id = store.create_experiment(plan, timestamp_ns=1)
        stage_id = "a" * 64
        attempt_id = store.register_attempt(
            experiment_id,
            stage_id=stage_id,
            ordinal=1,
            launch_nonce="fixture",
            source_sha256=plan.source_archive_sha256,
            config_sha256=plan.profile_identity_sha256,
        )
        reservation = store.reserve_budget(
            experiment_id,
            attempt_id=attempt_id,
            resource="gpu",
            cap_seconds=100,
        )
        assert store.budget_snapshot(experiment_id)["gpu_reserved_seconds"] == 100
    with ExperimentStore(database) as reopened:
        assert reopened.active_reservations(experiment_id) == (reservation,)
        assert (
            reopened.reconcile_reservation(
                reservation,
                measured_seconds=None,
                exit_established=False,
            )
            == 100
        )
        budget = reopened.budget_snapshot(experiment_id)
        assert budget["gpu_reserved_seconds"] == 0
        assert budget["gpu_charged_seconds"] == 100
        with pytest.raises(BudgetError, match="exceeds"):
            reopened.reserve_budget(
                experiment_id,
                attempt_id=attempt_id,
                resource="gpu",
                cap_seconds=21,
            )


def test_launch_requires_registered_attempt_and_prelaunch_reservation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite3"
    plan = _plan(tmp_path)
    with ExperimentStore(database) as store:
        experiment_id = store.create_experiment(plan, timestamp_ns=1)
        store.append_event(experiment_id, "PLAN_VALIDATED", {}, timestamp_ns=2)
        store.append_event(experiment_id, "PREFLIGHT_PASSED", {}, timestamp_ns=3)
        with pytest.raises(ValueError, match="attempt, reservation and device lease"):
            store.append_event(
                experiment_id,
                "WORKER_LAUNCHED",
                {
                    "attempt_id": "missing",
                    "reservation_id": "missing",
                    "lease_id": "missing",
                },
                timestamp_ns=4,
            )


def test_device_lease_is_exclusive_and_restart_safe(tmp_path: Path) -> None:
    database = tmp_path / "state.sqlite3"
    plan = _plan(tmp_path)
    with ExperimentStore(database) as store:
        experiment_id = store.create_experiment(plan, timestamp_ns=1)
        first = store.register_attempt(
            experiment_id,
            stage_id="a" * 64,
            ordinal=1,
            launch_nonce="first",
            source_sha256=plan.source_archive_sha256,
            config_sha256=plan.profile_identity_sha256,
        )
        second = store.register_attempt(
            experiment_id,
            stage_id="a" * 64,
            ordinal=2,
            launch_nonce="second",
            source_sha256=plan.source_archive_sha256,
            config_sha256=plan.profile_identity_sha256,
        )
        lease = store.acquire_device_lease(
            experiment_id,
            attempt_id=first,
            device_uuid=plan.target_gpu_uuid,
            launch_nonce="first",
            acquired_at_ns=2,
        )
        assert store.active_device_leases(experiment_id) == (lease,)
        with pytest.raises(ValueError, match="active lease"):
            store.acquire_device_lease(
                experiment_id,
                attempt_id=second,
                device_uuid=plan.target_gpu_uuid,
                launch_nonce="second",
                acquired_at_ns=3,
            )
    with ExperimentStore(database) as reopened:
        assert reopened.active_device_leases(experiment_id) == (lease,)
        reopened.release_device_lease(lease, released_at_ns=4)
        assert reopened.active_device_leases(experiment_id) == ()


def test_atomic_completion_marker_detects_corruption_and_missing_files(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "adapter.bin"
    artifact.write_bytes(b"verified bytes")
    stage_id = "a" * 64
    write_completion_marker(
        tmp_path,
        stage_id=stage_id,
        artifact_names=("adapter.bin",),
        evidence_class=EvidenceClass.SIMULATION,
    )
    inventory = verify_completion_marker(
        tmp_path,
        expected_stage_id=stage_id,
        expected_evidence_class=EvidenceClass.SIMULATION,
    )
    assert set(inventory) == {"adapter.bin"}

    artifact.write_bytes(b"corrupt bytes")
    with pytest.raises(ArtifactVerificationError, match="hash differs"):
        verify_completion_marker(
            tmp_path,
            expected_stage_id=stage_id,
            expected_evidence_class=EvidenceClass.SIMULATION,
        )
    artifact.unlink()
    with pytest.raises(ArtifactVerificationError, match="missing"):
        verify_completion_marker(
            tmp_path,
            expected_stage_id=stage_id,
            expected_evidence_class=EvidenceClass.SIMULATION,
        )


def test_simulation_evidence_can_never_cross_actual_admission_boundary(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite3"
    plan = _plan(tmp_path, simulation=True)
    with ExperimentStore(database) as store:
        experiment_id = store.create_experiment(plan, timestamp_ns=1)
        store.record_inventory(
            experiment_id,
            stage_id="a" * 64,
            inventory={"fixture.json": "b" * 64},
            evidence_class=EvidenceClass.SIMULATION,
        )
        with pytest.raises(EvidenceError, match="never qualify"):
            store.assert_actual_evidence(experiment_id)


def test_simulated_runtime_cannot_claim_named_host_acceptance(tmp_path: Path) -> None:
    database = tmp_path / "state.sqlite3"
    ratings = {"humour": 3, "surprise": 4, "distinctiveness": 5}
    report = run_rehearsal(
        database,
        tmp_path / "artifacts",
        review_ratings=ratings,
    )
    assert report["state"] == "COMPLETE"
    assert report["disposition"] == "TEST_ONLY"
    assert report["qualifies_candidate"] is False
    assert report["llm_calls"] == 0
    with ExperimentStore(database) as store:
        experiment_id = str(report["experiment_id"])
        assert store.replay(experiment_id) == ExperimentState.COMPLETE
        assert store.budget_snapshot(experiment_id)["gpu_charged_seconds"] == 37
        assert store.budget_snapshot(experiment_id)["cpu_charged_seconds"] == 11
        runtime = next(
            event
            for event in store.events(experiment_id)
            if event.event_type == "RUNTIME_QUALIFIED"
        )
        assert runtime.payload["named_host_acceptance"] is False
        assert runtime.payload["evidence_class"] == "simulation"


def test_rehearsal_requires_realistic_test_review_shape(tmp_path: Path) -> None:
    with pytest.raises(EvidenceError, match="three admitted fields"):
        run_rehearsal(
            tmp_path / "state.sqlite3",
            tmp_path / "artifacts",
            review_ratings={"humour": 3},
        )


def test_stale_checkpoint_is_rejected_before_resume(tmp_path: Path) -> None:
    source = "1" * 40
    binding = resolve_model_binding("primary")
    config = load_training_config("primary", mix=TrainingMix.OPERATIONAL)
    dataset = DatasetIdentity("a" * 64, "b" * 64, (), {})
    identity = expected_training_identity(
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=source,
    )
    (tmp_path / "training-identity.json").write_text(
        canonical_json(identity) + "\n",
        encoding="utf-8",
    )
    assert (
        verify_resumable_checkpoint(
            tmp_path,
            binding=binding,
            config=config,
            dataset=dataset,
            source_revision=source,
        )
        == identity["training_identity"]
    )
    with pytest.raises(CampaignIntegrityError, match="source/model/config/dataset"):
        verify_resumable_checkpoint(
            tmp_path,
            binding=binding,
            config=config,
            dataset=dataset,
            source_revision="2" * 40,
        )


def test_gpu_failure_is_preserved_and_does_not_refund_unknown_time(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite3"
    plan = _plan(tmp_path)
    with ExperimentStore(database) as store:
        experiment_id = store.create_experiment(plan, timestamp_ns=1)
        store.append_event(experiment_id, "PLAN_VALIDATED", {}, timestamp_ns=2)
        store.append_event(experiment_id, "PREFLIGHT_PASSED", {}, timestamp_ns=3)
        attempt_id = store.register_attempt(
            experiment_id,
            stage_id="a" * 64,
            ordinal=1,
            launch_nonce="gpu-failure",
            source_sha256=plan.source_archive_sha256,
            config_sha256=plan.profile_identity_sha256,
        )
        lease = store.acquire_device_lease(
            experiment_id,
            attempt_id=attempt_id,
            device_uuid=plan.target_gpu_uuid,
            launch_nonce="gpu-failure",
            acquired_at_ns=4,
        )
        reservation = store.reserve_budget(
            experiment_id,
            attempt_id=attempt_id,
            resource="gpu",
            cap_seconds=80,
        )
        store.append_event(
            experiment_id,
            "WORKER_LAUNCHED",
            {
                "attempt_id": attempt_id,
                "reservation_id": reservation,
                "lease_id": lease,
            },
            timestamp_ns=5,
        )
        store.reconcile_reservation(
            reservation,
            measured_seconds=None,
            exit_established=False,
        )
        store.release_device_lease(lease, released_at_ns=6)
        store.append_event(
            experiment_id,
            "WORKER_FAILED",
            {"code": "simulated-cuda-oom"},
            timestamp_ns=7,
        )
        assert store.state(experiment_id) == ExperimentState.FAILED
        assert store.budget_snapshot(experiment_id)["gpu_charged_seconds"] == 80
        assert store.events(experiment_id)[-1].payload["code"] == "simulated-cuda-oom"


def test_completion_report_is_canonical_json(tmp_path: Path) -> None:
    report = run_rehearsal(
        tmp_path / "state.sqlite3",
        tmp_path / "artifacts",
        review_ratings={"humour": 2, "surprise": 3, "distinctiveness": 4},
    )
    stored = json.loads(
        (tmp_path / "artifacts" / "rehearsal-report.json").read_text()
    )
    assert stored == report
