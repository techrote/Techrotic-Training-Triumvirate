"""Fault-injection coverage at the deterministic controller boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from techrotic_training_triumvirate.experiments import (
    EventKind,
    ExperimentPlan,
    ExperimentState,
    ExperimentStore,
    VerifiedEvent,
    verify_export,
)
from techrotic_training_triumvirate.experiments.worker import (
    WorkerHostError,
    WorkerSpec,
    run_host,
    write_spec,
)
from techrotic_training_triumvirate.runtime import RuntimeProtocolError


def _plan(tmp_path: Path) -> ExperimentPlan:
    return ExperimentPlan(
        allocation_id="fault-test",
        created_at="2026-10-24T20:00:00Z",
        source_archive_sha256="1" * 64,
        semantic_commit="2" * 40,
        model_id="model",
        model_sha256="3" * 64,
        tokenizer_sha256="4" * 64,
        dataset_sha256="5" * 64,
        config_sha256="6" * 64,
        gpu_uuid="GPU-22222222-2222-2222-2222-222222222222",
        gpu_hours=1.0,
        artifact_root=str(tmp_path),
        candidate_ids=("candidate",),
    )


def _event(kind: EventKind, index: int, **payload: object) -> VerifiedEvent:
    return VerifiedEvent(
        event_id=f"fault-{index}",
        kind=kind,
        timestamp=f"2026-10-24T20:00:{index:02d}Z",
        payload=payload,
    )


def test_gpu_failure_is_preserved_and_unknown_runtime_keeps_full_charge(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite"
    plan = _plan(tmp_path)
    attempt = plan.attempt_id("training", ordinal=1, launch_nonce="gpu-failure")
    with ExperimentStore(database) as store:
        store.create_plan(plan)
        store.append_event(plan.experiment_id, _event(EventKind.PLAN_VALIDATED, 1))
        store.append_event(plan.experiment_id, _event(EventKind.PREFLIGHT_PASSED, 2))
        store.reserve_budget(plan.experiment_id, attempt, 0.4)
        store.acquire_device_lease(
            plan.experiment_id,
            attempt,
            acquired_at="2026-10-24T20:00:02Z",
        )
        assert (
            store.append_event(
                plan.experiment_id,
                _event(EventKind.WORKER_LAUNCHED, 3, attempt_id=attempt),
            )
            is ExperimentState.TRAINING
        )
        assert (
            store.append_event(
                plan.experiment_id,
                _event(EventKind.FAILED, 4, reason="cuda_oom"),
            )
            is ExperimentState.FAILED
        )

    with ExperimentStore(database) as store:
        state, _ = store.replay(plan.experiment_id)
        assert state is ExperimentState.FAILED
        snapshot = store.reconcile_budget(
            plan.experiment_id,
            attempt,
            actual_hours=None,
            lifetime_established=False,
        )
        assert snapshot["committed_gpu_hours"] == 0.4
        store.release_device_lease(plan.experiment_id, attempt)


def test_missing_and_corrupted_export_outputs_fail_closed(tmp_path: Path) -> None:
    export = tmp_path / "export"
    export.mkdir()
    with pytest.raises(RuntimeProtocolError):
        verify_export(export)

    (export / "export-manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeProtocolError):
        verify_export(export)


def test_prelaunch_worker_failure_produces_no_completion_marker(tmp_path: Path) -> None:
    spec = WorkerSpec(
        attempt_id="attempt-prelaunch",
        argv=(str(tmp_path / "missing-worker.exe"),),
        cwd=str(tmp_path),
        environment={},
        deadline_seconds=1.0,
        artifact_root=str(tmp_path),
        source_hash="a" * 64,
        config_hash="b" * 64,
        launch_nonce="prelaunch-failure",
    )
    spec_path = tmp_path / "worker-spec.json"
    write_spec(spec_path, spec)
    with pytest.raises(WorkerHostError, match="executable"):
        run_host(spec_path)
    assert not (tmp_path / "attempt-prelaunch/host-complete.json").exists()
