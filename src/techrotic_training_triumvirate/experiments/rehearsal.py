"""Complete deterministic test-only experiment rehearsal with zero LLM calls."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    canonical_json,
    content_hash,
)
from techrotic_training_triumvirate.training.export import sha256_file

from .artifacts import verify_completion_marker, write_completion_marker
from .model import (
    EvidenceClass,
    ExperimentPlan,
    ExperimentState,
    semantic_stage_identity,
)
from .store import ExperimentStore


TITAN_UUID = "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8"


def simulation_plan(artifact_root: str | Path) -> ExperimentPlan:
    """Return a fixed plan whose identity is stable for the supplied root."""

    return ExperimentPlan(
        source_archive_sha256="1" * 64,
        semantic_commit="2" * 40,
        model_identity_sha256="3" * 64,
        dataset_identity_sha256="4" * 64,
        profile_identity_sha256="5" * 64,
        target_gpu_uuid=TITAN_UUID,
        gpu_budget_seconds=600,
        cpu_budget_seconds=300,
        artifact_root=str(Path(artifact_root)),
        simulation=True,
    )


def _write_json(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def _stage_fixture(
    store: ExperimentStore,
    experiment_id: str,
    *,
    root: Path,
    stage: ExperimentState,
    inputs: JsonObject,
    filename: str,
    payload: JsonObject,
) -> str:
    plan = store.load_plan(experiment_id)
    stage_id = semantic_stage_identity(plan, stage, inputs)
    directory = root / stage.value.lower()
    _write_json(directory / filename, payload)
    write_completion_marker(
        directory,
        stage_id=stage_id,
        artifact_names=(filename,),
        evidence_class=EvidenceClass.SIMULATION,
    )
    inventory = verify_completion_marker(
        directory,
        expected_stage_id=stage_id,
        expected_evidence_class=EvidenceClass.SIMULATION,
    )
    store.record_inventory(
        experiment_id,
        stage_id=stage_id,
        inventory=inventory,
        evidence_class=EvidenceClass.SIMULATION,
    )
    return stage_id


def run_rehearsal(
    database: str | Path,
    artifact_root: str | Path,
    *,
    review_ratings: Mapping[str, int],
) -> JsonObject:
    """Execute every controller stage with deterministic doubles and test review."""

    root = Path(artifact_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan = simulation_plan(root)
    timestamp = 1_800_000_000_000_000_000

    def next_time() -> int:
        nonlocal timestamp
        timestamp += 1_000
        return timestamp

    with ExperimentStore(database) as store:
        experiment_id = store.create_experiment(plan, timestamp_ns=next_time())
        store.append_event(
            experiment_id,
            "PLAN_VALIDATED",
            {"plan_sha256": content_hash(plan.to_object()), "llm_calls": 0},
            timestamp_ns=next_time(),
        )

        preflight_stage = _stage_fixture(
            store,
            experiment_id,
            root=root,
            stage=ExperimentState.PREFLIGHT,
            inputs={"source_archive_sha256": plan.source_archive_sha256},
            filename="preflight.json",
            payload={
                "schema": "ttt.simulated_preflight",
                "schema_version": 1,
                "test_only": True,
                "device_uuid": plan.target_gpu_uuid,
                "source_import_verified": True,
                "corpus_behavior_verified": True,
            },
        )
        store.append_event(
            experiment_id,
            "PREFLIGHT_PASSED",
            {
                "stage_id": preflight_stage,
                "evidence_class": EvidenceClass.SIMULATION.value,
            },
            timestamp_ns=next_time(),
        )

        training_stage = semantic_stage_identity(
            plan,
            ExperimentState.TRAINING,
            {"preflight_stage_id": preflight_stage},
        )
        attempt_id = store.register_attempt(
            experiment_id,
            stage_id=training_stage,
            ordinal=1,
            launch_nonce="simulation-attempt-01",
            source_sha256=plan.source_archive_sha256,
            config_sha256=plan.profile_identity_sha256,
        )
        lease_id = store.acquire_device_lease(
            experiment_id,
            attempt_id=attempt_id,
            device_uuid=plan.target_gpu_uuid,
            launch_nonce="simulation-attempt-01",
            acquired_at_ns=next_time(),
        )
        reservation_id = store.reserve_budget(
            experiment_id,
            attempt_id=attempt_id,
            resource="gpu",
            cap_seconds=120,
        )
        store.append_event(
            experiment_id,
            "WORKER_LAUNCHED",
            {
                "attempt_id": attempt_id,
                "reservation_id": reservation_id,
                "lease_id": lease_id,
                "simulated_worker": True,
            },
            timestamp_ns=next_time(),
        )
        training_dir = root / "training"
        _write_json(
            training_dir / "adapter.json",
            {
                "schema": "ttt.simulated_adapter",
                "schema_version": 1,
                "test_only": True,
                "attempt_id": attempt_id,
            },
        )
        write_completion_marker(
            training_dir,
            stage_id=training_stage,
            artifact_names=("adapter.json",),
            evidence_class=EvidenceClass.SIMULATION,
        )
        training_inventory = verify_completion_marker(
            training_dir,
            expected_stage_id=training_stage,
            expected_evidence_class=EvidenceClass.SIMULATION,
        )
        store.record_inventory(
            experiment_id,
            stage_id=training_stage,
            inventory=training_inventory,
            evidence_class=EvidenceClass.SIMULATION,
        )
        store.reconcile_reservation(
            reservation_id,
            measured_seconds=37,
            exit_established=True,
        )
        store.release_device_lease(
            lease_id,
            released_at_ns=next_time(),
        )
        store.append_event(
            experiment_id,
            "TRAINING_VERIFIED",
            {
                "stage_id": training_stage,
                "completion_marker_verified": True,
                "test_only": True,
            },
            timestamp_ns=next_time(),
        )

        store.append_event(
            experiment_id,
            "DEVELOPMENT_STARTED",
            {"parent_stage_id": training_stage},
            timestamp_ns=next_time(),
        )
        development_stage = _stage_fixture(
            store,
            experiment_id,
            root=root,
            stage=ExperimentState.DEVELOPMENT,
            inputs={"training_stage_id": training_stage},
            filename="development.json",
            payload={
                "schema": "ttt.simulated_development",
                "schema_version": 1,
                "test_only": True,
                "short_session_passed": True,
                "long_session_passed": True,
            },
        )
        candidate_id = content_hash(
            {
                "experiment_id": experiment_id,
                "training_stage_id": training_stage,
                "development_stage_id": development_stage,
            }
        )
        store.append_event(
            experiment_id,
            "CANDIDATE_SELECTED",
            {
                "candidate_id": candidate_id,
                "stage_id": development_stage,
                "test_only": True,
            },
            timestamp_ns=next_time(),
        )

        export_stage = semantic_stage_identity(
            plan,
            ExperimentState.EXPORTING,
            {"candidate_id": candidate_id},
        )
        export_attempt = store.register_attempt(
            experiment_id,
            stage_id=export_stage,
            ordinal=1,
            launch_nonce="simulation-export-01",
            source_sha256=plan.source_archive_sha256,
            config_sha256=plan.profile_identity_sha256,
        )
        cpu_reservation = store.reserve_budget(
            experiment_id,
            attempt_id=export_attempt,
            resource="cpu",
            cap_seconds=90,
        )
        store.append_event(
            experiment_id,
            "EXPORT_STARTED",
            {"candidate_id": candidate_id, "cpu_reservation": cpu_reservation},
            timestamp_ns=next_time(),
        )
        export_dir = root / "exporting"
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "fixture-q4.gguf").write_bytes(
            b"TTT SIMULATION FIXTURE - NOT TRAINED MODEL WEIGHTS\n"
        )
        _write_json(
            export_dir / "export.json",
            {
                "schema": "ttt.simulated_export",
                "schema_version": 1,
                "test_only": True,
                "candidate_id": candidate_id,
                "gguf_sha256": sha256_file(export_dir / "fixture-q4.gguf"),
            },
        )
        write_completion_marker(
            export_dir,
            stage_id=export_stage,
            artifact_names=("export.json", "fixture-q4.gguf"),
            evidence_class=EvidenceClass.SIMULATION,
        )
        export_inventory = verify_completion_marker(
            export_dir,
            expected_stage_id=export_stage,
            expected_evidence_class=EvidenceClass.SIMULATION,
        )
        store.record_inventory(
            experiment_id,
            stage_id=export_stage,
            inventory=export_inventory,
            evidence_class=EvidenceClass.SIMULATION,
        )
        store.reconcile_reservation(
            cpu_reservation,
            measured_seconds=11,
            exit_established=True,
        )
        store.append_event(
            experiment_id,
            "EXPORT_VERIFIED",
            {"stage_id": export_stage, "test_only": True, "q4_fixture": True},
            timestamp_ns=next_time(),
        )
        store.append_event(
            experiment_id,
            "RUNTIME_QUALIFIED",
            {
                "evidence_class": EvidenceClass.SIMULATION.value,
                "named_host_acceptance": False,
                "test_only": True,
            },
            timestamp_ns=next_time(),
        )

        frozen_stage = _stage_fixture(
            store,
            experiment_id,
            root=root,
            stage=ExperimentState.FROZEN_EVALUATION,
            inputs={"candidate_id": candidate_id},
            filename="frozen-evaluation.json",
            payload={
                "schema": "ttt.simulated_frozen_evaluation",
                "schema_version": 1,
                "candidate_id": candidate_id,
                "test_only": True,
                "trace_replay_verified": True,
            },
        )
        store.append_event(
            experiment_id,
            "FROZEN_EVALUATION_PASSED",
            {"stage_id": frozen_stage, "test_only": True},
            timestamp_ns=next_time(),
        )

        packet_id = content_hash(
            {
                "experiment_id": experiment_id,
                "candidate_id": candidate_id,
                "packet": "test-review",
            }
        )
        review_id = store.record_review(
            experiment_id,
            candidate_id=candidate_id,
            packet_id=packet_id,
            ratings=review_ratings,
            review_class="test",
            imported_at_ns=next_time(),
        )
        store.append_event(
            experiment_id,
            "HUMAN_REVIEW_IMPORTED",
            {
                "review_id": review_id,
                "review_class": "test",
                "candidate_id": candidate_id,
                "test_only": True,
            },
            timestamp_ns=next_time(),
        )
        store.append_event(
            experiment_id,
            "DISPOSITION_VERIFIED",
            {
                "outcome": "TEST_ONLY",
                "candidate_id": candidate_id,
                "qualifies_candidate": False,
            },
            timestamp_ns=next_time(),
        )

        final_state = store.replay(experiment_id)
        events = store.events(experiment_id)
        report: JsonObject = {
            "schema": "ttt.experiment_rehearsal",
            "schema_version": 1,
            "experiment_id": experiment_id,
            "state": final_state.value,
            "event_count": len(events),
            "last_event_hash": events[-1].event_hash,
            "budget": store.budget_snapshot(experiment_id),
            "evidence_class": EvidenceClass.SIMULATION.value,
            "llm_calls": 0,
            "qualifies_candidate": False,
            "disposition": "TEST_ONLY",
            "review_id": review_id,
        }
        if final_state != ExperimentState.COMPLETE:
            raise AssertionError("deterministic rehearsal did not complete")
        _write_json(root / "rehearsal-report.json", report)
        return report
