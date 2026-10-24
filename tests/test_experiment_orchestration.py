"""Deterministic controller persistence, replay, accounting and rehearsal tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from techrotic_training_triumvirate.experiments import (
    EvidenceClass,
    EventKind,
    ExperimentContractError,
    ExperimentPlan,
    ExperimentState,
    ExperimentStore,
    ExperimentStoreError,
    HumanReview,
    VerifiedEvent,
    assert_admission_eligible,
    run_rehearsal,
)


def _plan(tmp_path: Path, *, allocation: str = "alloc-1") -> ExperimentPlan:
    return ExperimentPlan(
        allocation_id=allocation,
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


def _event(kind: EventKind, index: int = 1, **payload: object) -> VerifiedEvent:
    return VerifiedEvent(
        event_id=f"event-{index}",
        kind=kind,
        timestamp=f"2026-10-24T20:00:{index:02d}Z",
        payload=payload,
    )


def test_plan_stage_and_attempt_identity_are_content_addressed(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    changed = replace(plan, config_sha256="7" * 64)
    assert plan.experiment_id != changed.experiment_id
    assert plan.stage_id("training") == plan.stage_id("training")
    assert plan.stage_id("training") != plan.stage_id("export")
    assert plan.attempt_id("training", ordinal=1, launch_nonce="a") != plan.attempt_id(
        "training", ordinal=2, launch_nonce="a"
    )


def test_events_are_idempotent_and_full_chain_replays_after_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite"
    plan = _plan(tmp_path)
    first = _event(EventKind.PLAN_VALIDATED)
    with ExperimentStore(database) as store:
        store.create_plan(plan)
        assert store.append_event(plan.experiment_id, first) is ExperimentState.PREFLIGHT
        assert store.append_event(plan.experiment_id, first) is ExperimentState.PREFLIGHT
        with pytest.raises(ExperimentStoreError, match="different verified"):
            store.append_event(
                plan.experiment_id,
                VerifiedEvent(
                    event_id=first.event_id,
                    kind=first.kind,
                    timestamp="2026-10-24T20:01:00Z",
                    payload={},
                ),
            )
        store.append_event(plan.experiment_id, _event(EventKind.PREFLIGHT_PASSED, 2))

    with ExperimentStore(database) as store:
        state, hashes = store.replay(plan.experiment_id)
        assert state is ExperimentState.READY
        assert len(hashes) == 2
        assert hashes[0] != hashes[1]


def test_invalid_transition_fails_without_mutating_state(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    with ExperimentStore(tmp_path / "state.sqlite") as store:
        store.create_plan(plan)
        with pytest.raises(ExperimentContractError, match="invalid"):
            store.append_event(plan.experiment_id, _event(EventKind.PREFLIGHT_PASSED))
        assert store.state(plan.experiment_id) is ExperimentState.PLANNED


def test_budget_reservation_survives_restart_and_unknown_lifetime_is_fully_charged(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite"
    plan = _plan(tmp_path)
    attempt = plan.attempt_id("training", ordinal=1, launch_nonce="n1")
    with ExperimentStore(database) as store:
        store.create_plan(plan)
        snapshot = store.reserve_budget(plan.experiment_id, attempt, 0.75)
        assert snapshot["committed_gpu_hours"] == 0.75

    with ExperimentStore(database) as store:
        assert store.budget_snapshot(plan.experiment_id)["committed_gpu_hours"] == 0.75
        snapshot = store.reconcile_budget(
            plan.experiment_id,
            attempt,
            actual_hours=None,
            lifetime_established=False,
        )
        assert snapshot["committed_gpu_hours"] == 0.75
        second = plan.attempt_id("training", ordinal=2, launch_nonce="n2")
        with pytest.raises(ExperimentStoreError, match="exhausted"):
            store.reserve_budget(plan.experiment_id, second, 0.3)


def test_physical_device_lease_is_exclusive_across_experiments(tmp_path: Path) -> None:
    first = _plan(tmp_path, allocation="first")
    second = _plan(tmp_path, allocation="second")
    database = tmp_path / "state.sqlite"
    with ExperimentStore(database) as store:
        for plan in (first, second):
            store.create_plan(plan)
            attempt = plan.attempt_id("training", ordinal=1, launch_nonce=plan.allocation_id)
            store.reserve_budget(plan.experiment_id, attempt, 0.1)
        first_attempt = first.attempt_id(
            "training", ordinal=1, launch_nonce=first.allocation_id
        )
        second_attempt = second.attempt_id(
            "training", ordinal=1, launch_nonce=second.allocation_id
        )
        store.acquire_device_lease(
            first.experiment_id, first_attempt, acquired_at="2026-10-24T20:00:00Z"
        )
        with pytest.raises(ExperimentStoreError, match="active lease"):
            store.acquire_device_lease(
                second.experiment_id,
                second_attempt,
                acquired_at="2026-10-24T20:00:01Z",
            )
        store.release_device_lease(first.experiment_id, first_attempt)
        store.acquire_device_lease(
            second.experiment_id,
            second_attempt,
            acquired_at="2026-10-24T20:00:02Z",
        )


def test_simulation_artifact_can_never_be_marked_admission_eligible(
    tmp_path: Path,
) -> None:
    plan = replace(_plan(tmp_path), evidence_class=EvidenceClass.SIMULATION)
    with ExperimentStore(tmp_path / "state.sqlite") as store:
        store.create_plan(plan)
        with pytest.raises(ExperimentStoreError, match="never"):
            store.record_artifact(
                plan.experiment_id,
                name="fake",
                path=str(tmp_path / "fake.json"),
                sha256="a" * 64,
                evidence_class=EvidenceClass.SIMULATION,
                admission_eligible=True,
            )


def test_end_to_end_rehearsal_reaches_complete_with_zero_llm_calls_but_not_admission(
    tmp_path: Path,
) -> None:
    review = HumanReview(
        reviewer_id="pytest",
        submitted_at="2026-01-01T00:00:11Z",
        packet_id="packet-1",
        candidate_id="candidate-double",
        humour=3,
        surprise=4,
        distinctiveness=5,
        test_fixture=True,
    )
    result = run_rehearsal(
        tmp_path / "rehearsal.sqlite", tmp_path / "artifacts", review=review
    )
    assert result["state"] == "COMPLETE"
    assert result["llm_calls"] == 0
    assert result["evidence_class"] == "simulation"
    assert result["admission_eligible"] is False
    with pytest.raises(ValueError, match="cannot satisfy admission"):
        assert_admission_eligible(result)
