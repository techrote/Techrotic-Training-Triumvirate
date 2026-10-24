"""Hardening regressions for TTT-018 non-GPU completion contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from techrotic_training_triumvirate.experiments import (
    CompletionMarkerError,
    CpuDiagnosticSpec,
    CpuQ4QualificationSpec,
    EventKind,
    EvidenceClass,
    ExperimentPlan,
    ExperimentState,
    ExperimentStore,
    PipelineAdapterError,
    VerifiedEvent,
    assert_admission_eligible,
    run_cpu_q4_qualification,
    verify_checkpoint,
    verify_completion_marker,
    write_completion_marker,
)
from techrotic_training_triumvirate.experiments.worker import WorkerSpec
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


def _plan(tmp_path: Path) -> ExperimentPlan:
    return ExperimentPlan(
        allocation_id="hardening",
        created_at="2026-10-24T22:30:00Z",
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


def _event(kind: EventKind, index: int) -> VerifiedEvent:
    return VerifiedEvent(
        event_id=f"hardening-{index}-{kind.value.lower()}",
        kind=kind,
        timestamp=f"2026-10-24T22:30:{index:02d}Z",
        payload={},
    )


def test_completion_marker_fails_closed_on_corrupt_or_missing_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "adapter.bin"
    artifact.write_bytes(b"verified")
    stage_id = "ttt-stage-hardening"
    record = write_completion_marker(
        tmp_path,
        stage_id=stage_id,
        artifact_names=("adapter.bin",),
        evidence_class=EvidenceClass.SIMULATION,
    )
    verified = verify_completion_marker(
        tmp_path,
        stage_id=stage_id,
        evidence_class=EvidenceClass.SIMULATION,
    )
    assert verified == record

    artifact.write_bytes(b"corrupt")
    with pytest.raises(CompletionMarkerError, match="hash differs"):
        write_completion_marker(
            tmp_path,
            stage_id=stage_id,
            artifact_names=("adapter.bin",),
            evidence_class=EvidenceClass.SIMULATION,
        )
    with pytest.raises(CompletionMarkerError, match="hash differs"):
        verify_completion_marker(
            tmp_path,
            stage_id=stage_id,
            evidence_class=EvidenceClass.SIMULATION,
        )

    artifact.unlink()
    with pytest.raises(CompletionMarkerError, match="missing"):
        verify_completion_marker(
            tmp_path,
            stage_id=stage_id,
            evidence_class=EvidenceClass.SIMULATION,
        )


def test_checkpoint_resume_rejects_changed_source_identity(tmp_path: Path) -> None:
    source_revision = "1" * 40
    binding = resolve_model_binding("primary")
    config = load_training_config("primary", mix=TrainingMix.OPERATIONAL)
    dataset = DatasetIdentity("a" * 64, "b" * 64, (), {})
    identity = expected_training_identity(
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=source_revision,
    )
    (tmp_path / "training-identity.json").write_text(
        canonical_json(identity) + "\n",
        encoding="utf-8",
    )

    result = verify_checkpoint(
        tmp_path,
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=source_revision,
    )
    assert result["training_identity"] == identity["training_identity"]

    with pytest.raises(CampaignIntegrityError, match="source/model/config/dataset"):
        verify_checkpoint(
            tmp_path,
            binding=binding,
            config=config,
            dataset=dataset,
            source_revision="2" * 40,
        )


def test_cpu_q4_chain_executes_real_subprocesses_but_never_qualifies(
    tmp_path: Path,
) -> None:
    tool = Path(sys.executable)
    f16 = tmp_path / "model-f16.gguf"
    q4 = tmp_path / "model-q4.gguf"

    conversion = CpuDiagnosticSpec(
        tool=tool,
        args=(
            "-c",
            f"from pathlib import Path; Path({str(f16)!r}).write_bytes(b'f16')",
        ),
        cwd=tmp_path,
        output_dir=tmp_path / "conversion",
        timeout_seconds=10,
        artifact=f16,
        threads=1,
    )
    quantization = CpuDiagnosticSpec(
        tool=tool,
        args=(
            "-c",
            (
                "from pathlib import Path; "
                f"s=Path({str(f16)!r}); d=Path({str(q4)!r}); "
                "d.write_bytes(s.read_bytes()+b'-q4')"
            ),
        ),
        cwd=tmp_path,
        output_dir=tmp_path / "quantization",
        timeout_seconds=10,
        artifact=q4,
        threads=1,
    )
    inference = CpuDiagnosticSpec(
        tool=tool,
        args=(
            "-c",
            (
                "import os; from pathlib import Path; "
                "assert os.environ['CUDA_VISIBLE_DEVICES']==''; "
                f"print(len(Path({str(q4)!r}).read_bytes()))"
            ),
        ),
        cwd=tmp_path,
        output_dir=tmp_path / "inference",
        timeout_seconds=10,
        threads=1,
    )

    result = run_cpu_q4_qualification(
        CpuQ4QualificationSpec(
            conversion=conversion,
            quantization=quantization,
            inference=inference,
            f16_artifact=f16,
            q4_artifact=q4,
            output_dir=tmp_path / "qualification",
        )
    )
    assert result["evidence_class"] == "cpu-diagnostic"
    assert result["admission_eligible"] is False
    assert result["named_host_acceptance"] is False
    assert result["f16"]["sha256"] != result["q4"]["sha256"]
    assert result["stages"]["inference"]["cpu_threads"] == 1
    with pytest.raises(PipelineAdapterError, match="cannot satisfy admission"):
        assert_admission_eligible(result)


def test_cancellation_reaches_terminal_cancelled_state_after_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite"
    plan = _plan(tmp_path)
    with ExperimentStore(database) as store:
        store.create_plan(plan)
        store.append_event(plan.experiment_id, _event(EventKind.PLAN_VALIDATED, 1))
        state = store.append_event(
            plan.experiment_id,
            _event(EventKind.CANCEL_REQUESTED, 2),
        )
        assert state is ExperimentState.CANCELLING

    with ExperimentStore(database) as store:
        state, _ = store.replay(plan.experiment_id)
        assert state is ExperimentState.CANCELLING
        state = store.append_event(
            plan.experiment_id,
            _event(EventKind.CANCELLED, 3),
        )
        assert state is ExperimentState.CANCELLED
        replayed, _ = store.replay(plan.experiment_id)
        assert replayed is ExperimentState.CANCELLED


def test_worker_spec_reads_pre_hardening_spec_with_default_grace(
    tmp_path: Path,
) -> None:
    raw = WorkerSpec(
        attempt_id="attempt",
        argv=(sys.executable, "-c", "print('ok')"),
        cwd=str(tmp_path),
        environment={},
        deadline_seconds=10,
        artifact_root=str(tmp_path),
        source_hash="a" * 64,
        config_hash="b" * 64,
        launch_nonce="nonce",
    ).to_object()
    raw.pop("grace_seconds")
    restored = WorkerSpec.from_object(raw)
    assert restored.grace_seconds == 5.0
