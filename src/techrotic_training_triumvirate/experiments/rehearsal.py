"""GPU-free end-to-end rehearsal of the deterministic experiment state machine."""

from __future__ import annotations

from pathlib import Path

from techrotic_training_triumvirate.schemas import JsonObject, canonical_json, content_hash
from techrotic_training_triumvirate.training.export import sha256_file

from .model import (
    EvidenceClass,
    EventKind,
    ExperimentContractError,
    ExperimentPlan,
    HumanReview,
    VerifiedEvent,
)
from .store import ExperimentStore


def _event(index: int, kind: EventKind, payload: JsonObject | None = None) -> VerifiedEvent:
    return VerifiedEvent(
        event_id=f"rehearsal-{index:02d}-{kind.value.lower()}",
        kind=kind,
        timestamp=f"2026-01-01T00:00:{index:02d}Z",
        payload=payload or {},
    )


def run_rehearsal(
    database: str | Path, output: str | Path, *, review: HumanReview
) -> JsonObject:
    """Run every promotion gate with deterministic doubles and zero LLM calls."""

    if not review.test_fixture:
        raise ExperimentContractError(
            "rehearsal requires an explicitly marked test review record"
        )
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan = ExperimentPlan(
        allocation_id="simulation-allocation",
        created_at="2026-01-01T00:00:00Z",
        source_archive_sha256="1" * 64,
        semantic_commit="2" * 40,
        model_id="deterministic-double",
        model_sha256="3" * 64,
        tokenizer_sha256="4" * 64,
        dataset_sha256="5" * 64,
        config_sha256="6" * 64,
        gpu_uuid="GPU-00000000-0000-0000-0000-000000000001",
        gpu_hours=1.0,
        artifact_root=str(root),
        candidate_ids=(review.candidate_id,),
        evidence_class=EvidenceClass.SIMULATION,
    )
    with ExperimentStore(database) as store:
        experiment_id = store.create_plan(plan)
        attempt_id = plan.attempt_id(
            "training", ordinal=1, launch_nonce="simulation-launch"
        )
        store.append_event(experiment_id, _event(1, EventKind.PLAN_VALIDATED))
        store.append_event(experiment_id, _event(2, EventKind.PREFLIGHT_PASSED))
        store.reserve_budget(experiment_id, attempt_id, 0.25)
        store.acquire_device_lease(
            experiment_id, attempt_id, acquired_at="2026-01-01T00:00:02Z"
        )
        store.append_event(
            experiment_id,
            _event(3, EventKind.WORKER_LAUNCHED, {"attempt_id": attempt_id}),
        )
        store.append_event(
            experiment_id,
            _event(4, EventKind.TRAINING_VERIFIED, {"simulated": True}),
        )
        store.reconcile_budget(
            experiment_id,
            attempt_id,
            actual_hours=0.125,
            lifetime_established=True,
        )
        store.release_device_lease(experiment_id, attempt_id)
        store.append_event(experiment_id, _event(5, EventKind.DEVELOPMENT_STARTED))
        store.append_event(
            experiment_id,
            _event(6, EventKind.DEVELOPMENT_PASSED, {"simulated": True}),
        )
        store.append_event(experiment_id, _event(7, EventKind.EXPORT_STARTED))
        store.append_event(
            experiment_id,
            _event(8, EventKind.EXPORT_VERIFIED, {"simulated": True}),
        )
        store.append_event(
            experiment_id,
            _event(9, EventKind.RUNTIME_PASSED, {"simulated": True}),
        )
        store.append_event(
            experiment_id,
            _event(10, EventKind.FROZEN_PASSED, {"simulated": True}),
        )
        store.append_event(
            experiment_id,
            _event(11, EventKind.HUMAN_REVIEW_IMPORTED, review.to_object()),
        )
        store.append_event(
            experiment_id,
            _event(12, EventKind.ADMISSION_VERIFIED, {"simulated": True}),
        )

        simulation_path = root / "rehearsal-evidence.json"
        evidence: JsonObject = {
            "schema": "ttt.experiment_rehearsal",
            "schema_version": 1,
            "experiment_id": experiment_id,
            "candidate_id": review.candidate_id,
            "evidence_class": EvidenceClass.SIMULATION.value,
            "admission_eligible": False,
            "llm_calls": 0,
            "review": review.to_object(),
        }
        simulation_path.write_text(
            canonical_json(evidence) + "\n", encoding="utf-8", newline="\n"
        )
        store.record_artifact(
            experiment_id,
            name="rehearsal-evidence",
            path=str(simulation_path),
            sha256=sha256_file(simulation_path),
            evidence_class=EvidenceClass.SIMULATION,
            admission_eligible=False,
        )
        state, hashes = store.replay(experiment_id)
        budget = store.budget_snapshot(experiment_id)
        inventory = store.artifact_inventory(experiment_id)

    return {
        **evidence,
        "state": state.value,
        "event_chain_sha256": content_hash(list(hashes)),
        "budget": budget,
        "artifacts": list(inventory),
    }
