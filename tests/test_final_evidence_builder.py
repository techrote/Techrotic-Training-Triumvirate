"""Finalization refuses incomplete/corrupt runs and preserves negative findings."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from techrotic_training_triumvirate.evaluation.closedloop import ClosedLoopReport

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_final_evidence.py"
_SPEC = importlib.util.spec_from_file_location("final_evidence_builder", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


def _checksums(directory: Path) -> None:
    lines = [
        f"{builder.sha256(path)}  {path.relative_to(directory).as_posix()}"
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_incomplete_execution_does_not_write_or_replace_results(tmp_path: Path) -> None:
    destination = tmp_path / builder.FINAL
    destination.mkdir(parents=True)
    report = destination / "report.md"
    report.write_text("previous result", encoding="utf-8")
    data = destination / "data-card.md"
    data.write_text("owner-authored data", encoding="utf-8")
    with pytest.raises(builder.FinalEvidenceError, match="incomplete"):
        builder.build_final_evidence(tmp_path)
    assert report.read_text(encoding="utf-8") == "previous result"
    assert data.read_text(encoding="utf-8") == "owner-authored data"
    assert not (destination / "admission-package.json").exists()


def test_complete_marker_cannot_override_running_campaign(tmp_path: Path) -> None:
    portable, baseline = tmp_path / builder.PORTABLE, tmp_path / builder.BASELINE
    portable.mkdir(parents=True)
    baseline.mkdir(parents=True)
    (portable / "COMPLETE.json").write_text("{}", encoding="utf-8")
    (portable / "campaign.json").write_text(
        json.dumps(
            {
                "git_commit": builder.SOURCE_REVISION,
                "status": "running",
                "substantive_campaign_executed": False,
                "variants": {},
            }
        ),
        encoding="utf-8",
    )
    (baseline / "fixture.txt").write_text("negative test fixture", encoding="utf-8")
    _checksums(portable)
    _checksums(baseline)
    with pytest.raises(builder.FinalEvidenceError, match="all five"):
        builder.build_final_evidence(tmp_path)
    assert not (tmp_path / builder.FINAL / "report.md").exists()


def test_snapshot_checksum_requires_exact_files_and_actual_bytes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "evidence.json"
    source.write_text('{"status":"failed"}\n', encoding="utf-8")
    _checksums(tmp_path)
    builder.verify_checksums(tmp_path)
    source.write_text('{"status":"successful"}\n', encoding="utf-8")
    with pytest.raises(builder.FinalEvidenceError, match="hash mismatch"):
        builder.verify_checksums(tmp_path)
    _checksums(tmp_path)
    (tmp_path / "unhashed.json").write_text("{}", encoding="utf-8")
    with pytest.raises(builder.FinalEvidenceError, match="exact snapshot"):
        builder.verify_checksums(tmp_path)


@pytest.mark.parametrize("path", ["../outside.json", "C:/secrets", "a\\b", "/absolute"])
def test_snapshot_paths_cannot_escape(tmp_path: Path, path: str) -> None:
    with pytest.raises(builder.FinalEvidenceError, match="unsafe"):
        builder.safe_file(tmp_path, path)


def test_duplicate_checksum_entries_are_refused(tmp_path: Path) -> None:
    source = tmp_path / "failed.json"
    source.write_text("{}", encoding="utf-8")
    line = f"{builder.sha256(source)}  failed.json\n"
    (tmp_path / "SHA256SUMS").write_text(line + line, encoding="utf-8")
    with pytest.raises(builder.FinalEvidenceError, match="duplicate"):
        builder.verify_checksums(tmp_path)


def test_negative_metrics_are_not_promoted_by_parity_or_training_loss() -> None:
    # Deliberately failed synthetic metrics exercise aggregation only. They are
    # never emitted as an actual candidate report or labelled quality evidence.
    metrics = {
        "objective": {
            "objective_completion_rate": 0.0,
            "schema_valid_rate": 0.2,
            "accepted_command_rate": 0.0,
            "churn_rate": 1.0,
            "energy_used": 0,
        },
        "recovery": {"execution_failure_recovery_rate": 0.0},
        "hidden_information": {
            "secret_leakage_count": 1,
            "hidden_world_fact_text_match_count": 0,
            "fabricated_result_count": 1,
            "intercept_grounding_failure_count": 0,
            "critical_violation_count": 2,
        },
        "automated_character_proxies": {"repetition_rate": 1.0},
    }
    closed = ClosedLoopReport({"episodes": [{"metrics": metrics}]}, {"measured": False})
    frozen = {
        "policy": {"policy_id": "synthetic-failed-fixture"},
        "cases": [{"command_count": 3, "accepted_count": 0}],
        "operational": {
            "mechanical": {
                "score": 0.1,
                "rejection_recovery_rate": 0.0,
                "parse_valid_rate": 0.0,
            },
            "hidden_information": {
                "critical_violation_count": 2,
                "hidden_fact_use_count": 0,
            },
            "closed_loop": {},
        },
        "character": {"automated_proxies": {}},
    }
    training = {
        "parity": {"passed": True},
        "run_id": "fixture",
        "completed_steps": 1,
        "train_examples": 1,
        "training_metrics": {"train_loss": 0.0},
        "wall_seconds": 1.0,
        "run_manifest_sha256": "a" * 64,
    }
    metadata = {
        "variant": "joint",
        "base_checkpoint": {},
        "dataset_hash": "fixture",
        "decoding": {},
    }
    summary = builder.summarize_candidate(frozen, closed, metadata, training)
    assert summary["gates"]["export_parity"] is True
    assert summary["gates"]["frozen_evaluation"] is False
    assert summary["gates"]["closed_loop"] is False
    assert summary["gates"]["hidden_information"] is False
    assert summary["gates"]["runtime"] is False
    assert summary["gates"]["human_review"] is False
    assert all(value is None for value in summary["human_ratings"].values())
    assert summary["q4_runtime_measurements"] is None
    assert "Reject continued runtime integration" in builder._recommendation(summary)
    card = builder._card(summary, ["fixture/omitted.safetensors"])
    assert "NOT ADMITTED" in card
    assert "ratings remain null" in card
    assert "fixture/omitted.safetensors" in card
    frozen["cases"] = [{"command_count": 0, "accepted_count": 0}]
    frozen["operational"]["mechanical"].update(
        score=1.0, rejection_recovery_rate=1.0, parse_valid_rate=1.0
    )
    empty = builder.summarize_candidate(frozen, closed, metadata, training)
    assert empty["mechanical_score"] == 1.0  # Preserve frozen default convention.
    assert empty["gates"]["frozen_evaluation"] is False


def test_report_tables_keep_candidate_critical_counts_in_correct_table() -> None:
    def failed(variant: str, closed_count: int, frozen_count: int) -> dict:
        return {
            "variant": variant,
            "mechanical_score": 0.1,
            "rejection_recovery_rate": 0.0,
            "closed_loop_objective_rate": 0.0,
            "closed_loop_failure_recovery_rate": 0.0,
            "closed_loop_hidden_information": {
                "critical_violation_count": closed_count
            },
            "frozen_hidden_information": {"critical_violation_count": frozen_count},
            "frozen_accepted_command_count": 0,
            "frozen_command_count": 1,
            "frozen_schema_valid_rate": 0.0,
            "closed_loop_acceptance_rate": 0.0,
            "closed_loop_churn_rate": 1.0,
            "closed_loop_energy_used": 0,
            "closed_loop_communication_count": 2,
            "character": {
                "constraint_adherence_rate": 0.0,
                "repetition_rate": 1.0,
                "lexical_diversity": 0.1,
                "doctrine_consistency_rate": 0.0,
            },
            "native_inference_runtime": {"total_action_seconds": 1.0},
        }

    text = "\n".join(
        builder.report_tables(
            [failed("fixture-a", 2, 1), failed("fixture-b", 5, 2)],
            {"operational": {"mechanical": {"score": 0.99}}},
        )
    )
    mechanical_table = text.split("| Policy | Frozen accepted", 1)[0]
    assert (
        "| fixture-a | 0.100000 | 0.000000 | 0.000000 | 0.000000 | **3** |"
        in mechanical_table
    )
    assert (
        "| fixture-b | 0.100000 | 0.000000 | 0.000000 | 0.000000 | **7** |"
        in mechanical_table
    )
    warnings = text.split("Automated style warnings", 1)[1]
    assert "| fixture-" not in warnings
    assert "fixture-a: episode-averaged repetition proxy exceeds 0.50" in warnings
    assert "empty-episode convention" in warnings
    assert "does not imply that utterance was repeated" in text
    assert text.count("| fixture-a |") == 3
    assert text.count("| fixture-b |") == 3


def test_reporting_commit_is_separate_and_changed_tool_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = (
        "scripts/build_final_evidence.py",
        "src/techrotic_training_triumvirate/admission.py",
        "docs/rag/19-final-admission.md",
    )
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"committed tool fixture\n")

    def git(command: list[str], **kwargs: object) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=(b"c" * 40 + b"\n")
            if command[1] == "rev-parse"
            else b"committed tool fixture\n",
        )

    monkeypatch.setattr(builder.subprocess, "run", git)
    source = builder.reporter_source(tmp_path)
    assert source["reporting_source_revision"] == "c" * 40
    assert source["worker_source_revision"] == builder.SOURCE_REVISION
    assert source["reporting_source_revision"] != source["worker_source_revision"]
    (tmp_path / names[0]).write_bytes(b"committed tool fixture\r\n")
    windows_source = builder.reporter_source(tmp_path)
    assert (
        windows_source["reporting_source_matches_commit_after_crlf_normalization"]
        is True
    )
    assert (
        windows_source["reporting_file_sha256"][names[0]]
        != windows_source["committed_reporting_file_sha256"][names[0]]
    )
    (tmp_path / names[0]).write_bytes(b"uncommitted change")
    with pytest.raises(builder.FinalEvidenceError, match="uncommitted or changed"):
        builder.reporter_source(tmp_path)
