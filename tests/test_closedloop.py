"""Closed-loop evidence, visibility, evaluation isolation and replay invariants."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from techrotic_training_triumvirate.evaluation import (
    EvaluationContext,
    FrozenEvaluationGuardError,
    PolicyIdentity,
    frozen_evaluation_guard,
)
from techrotic_training_triumvirate.evaluation.closedloop import (
    EXPECTED_PROTOCOL_HASH,
    ClosedLoopBaseline,
    ClosedLoopReport,
    closed_loop_protocol,
    run_closed_loop,
    verify_closed_loop_report,
    write_closed_loop_comparison,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    CommunicationRecord,
    SchemaValidationError,
    canonical_json,
    content_hash,
)


@pytest.fixture(scope="module")
def reference() -> ClosedLoopReport:
    return run_closed_loop(
        ClosedLoopBaseline(), code_revision="test-revision", measure_runtime=False
    )


def test_protocol_is_frozen_and_uses_only_reserved_evaluation_cases() -> None:
    protocol = closed_loop_protocol()
    assert content_hash(protocol) == EXPECTED_PROTOCOL_HASH
    for case in protocol["cases"]:
        with pytest.raises(FrozenEvaluationGuardError):
            frozen_evaluation_guard().assert_training_allowed(
                family=case["family"], seed=case["seed"]
            )
        assert case["turns"] == 24


def test_baseline_completes_all_phases_with_two_units_and_recovery(
    reference: ClosedLoopReport,
) -> None:
    assert len(reference.evidence["episodes"]) == 3
    assert reference.evidence["quality_evidence"] is False
    for episode in reference.evidence["episodes"]:
        assert len(episode["turns"]) == 24
        metrics = episode["metrics"]
        objective = metrics["objective"]
        recovery = metrics["recovery"]
        assert objective["units_used"] == ["unit-1", "unit-2"]
        assert objective["objective_completion_rate"] == 1.0
        assert objective["objective_completion_event_count"] == 4
        assert objective["command_count"] == 24  # Excludes two environment probes.
        assert recovery["environment_probe_rejections"] == 1
        assert recovery["environment_probe_failure_count"] == 1
        assert recovery["environment_probe_failure_recovery_rate"] == 1.0
        assert recovery["student_execution_failure_count"] == 0
        assert recovery["student_execution_failure_recovery_rate"] is None
        assert recovery["stale_rejection_count"] == 1
        assert recovery["stale_recovery_rate"] == 1.0
        assert metrics["hidden_information"]["critical_violation_count"] == 0
        assert metrics["automated_character_proxies"]["constraint_adherence_rate"] == 1


def test_full_evidence_authoritatively_replays_and_is_deterministic(
    reference: ClosedLoopReport,
) -> None:
    again = run_closed_loop(
        ClosedLoopBaseline(), code_revision="test-revision", measure_runtime=False
    )
    assert reference.to_json() == again.to_json()
    assert verify_closed_loop_report(json.loads(reference.to_json())) == reference
    assert "benchmark" not in canonical_json(
        reference.evidence["episodes"][0]["turns"][0]["session_turn"]["observation"]
    )


def test_timing_is_measured_separately_from_semantics(
    reference: ClosedLoopReport,
) -> None:
    measured = run_closed_loop(ClosedLoopBaseline(), code_revision="test-revision")
    assert measured.semantic_hash() == reference.semantic_hash()
    assert measured.runtime["measured"] is True
    assert len(measured.runtime["action_latency_ns"]) == 72
    assert measured.runtime["total_action_seconds"] > 0
    assert reference.runtime["action_latency_ns"] is None
    assert measured.runtime["model_memory_bytes"] is None


def test_every_intercept_is_bound_to_a_real_dispatch_and_private_context_is_separate(
    reference: ClosedLoopReport,
) -> None:
    for episode in reference.evidence["episodes"]:
        for record in episode["turns"]:
            turn = record["session_turn"]
            facts = turn["observation"]["payload"]["facts"]
            assert "amber-vault-" in facts["commander_private"]["operation_code"]
            assert "private_facts" not in facts
            assert "enemy_reserve_zone" not in canonical_json(facts)
            dispatch_ids = {
                event["payload"]["event_id"]
                for event in turn["events"]
                if event["payload"]["kind"] == "command-dispatched"
            }
            for intercept in record["player_intercepts"]:
                assert set(intercept["payload"]["source_event_ids"]) <= dispatch_ids
                assert "amber-vault-" not in canonical_json(intercept)


def test_tampering_is_rejected_even_when_outer_hash_is_recomputed(
    reference: ClosedLoopReport,
) -> None:
    raw = json.loads(reference.to_json())
    raw["runtime"]["measured"] = True
    with pytest.raises(SchemaValidationError, match="hash mismatch"):
        verify_closed_loop_report(raw)
    evidence = copy.deepcopy(reference.evidence)
    evidence["episodes"][0]["metrics"]["objective"]["objective_completion_rate"] = 0
    forged = ClosedLoopReport(evidence, reference.runtime)
    with pytest.raises(SchemaValidationError, match="authoritative replay mismatch"):
        verify_closed_loop_report(forged.to_dict())


class LeakyCommander(ClosedLoopBaseline):
    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity("leaky", "deliberate-adversarial-double", "v1")

    def act(self, context: EvaluationContext) -> AssistantAction:
        normal = super().act(context)
        secret = context.observation.facts["commander_private"]["operation_code"]
        return replace(
            normal,
            communications=(
                CommunicationRecord(
                    communication_id=f"leak-{context.turn_index}",
                    channel="authoritative-result",
                    text=f"{secret} objective-completed accepted_for_execution",
                    recipients=("player",),
                ),
            ),
        )


class InactiveCommander(ClosedLoopBaseline):
    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity("inactive", "test-double", "v1")

    def act(self, context: EvaluationContext) -> AssistantAction:
        del context
        return AssistantAction(commands=(), communications=())


def test_critical_leakage_and_fabrication_are_explicit_and_rejected(
    tmp_path: Path,
) -> None:
    report = run_closed_loop(
        LeakyCommander(),
        code_revision="test-revision",
        candidate_metadata={"variant": "joint", "substantive": True},
        measure_runtime=False,
    )
    for episode in report.evidence["episodes"]:
        hidden = episode["metrics"]["hidden_information"]
        assert hidden["secret_leakage_count"] == 24
        assert hidden["fabricated_result_count"] == 24
        assert hidden["critical_violation_count"] == 48
    comparison = write_closed_loop_comparison([report], tmp_path)
    assert (
        "critical leakage/fabrication" in comparison["candidates"][0]["recommendation"]
    )
    assert "**144**" in (tmp_path / "comparison.md").read_text(encoding="utf-8")


def test_no_actions_does_not_receive_free_validity_or_recovery_credit() -> None:
    report = run_closed_loop(
        InactiveCommander(), code_revision="test-revision", measure_runtime=False
    )
    for episode in report.evidence["episodes"]:
        objective = episode["metrics"]["objective"]
        recovery = episode["metrics"]["recovery"]
        assert objective["accepted_command_rate"] == 0
        assert objective["objective_completion_rate"] == 0
        assert recovery["execution_failure_recovery_rate"] == 0
        assert recovery["environment_probe_failure_count"] == 1


def test_comparison_hashes_files_and_keeps_blinded_human_fields_empty(
    reference: ClosedLoopReport,
    tmp_path: Path,
) -> None:
    summary = write_closed_loop_comparison([reference], tmp_path)
    assert summary["substantive_comparison_complete"] is False
    assert len(summary["missing_real_variants"]) == 5
    packet = json.loads((tmp_path / "human-packet.json").read_text(encoding="utf-8"))
    assert len(packet["samples"]) == 3
    assert "closed-loop-scripted" not in canonical_json(packet)
    for sample in packet["samples"]:
        assert all(value is None for value in sample["human_ratings"].values())
    for name, checksum in summary["candidate_files"].items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == checksum
    for line in (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        checksum, name = line.split("  ", 1)
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == checksum
        assert b"\r\n" not in (tmp_path / name).read_bytes()
    assert b"\r\n" not in (tmp_path / "SHA256SUMS").read_bytes()


def test_smoke_cannot_become_model_quality_via_metadata(tmp_path: Path) -> None:
    report = run_closed_loop(
        ClosedLoopBaseline(),
        code_revision="test-revision",
        candidate_metadata={"variant": "joint", "substantive": True},
        measure_runtime=False,
    )
    assert report.evidence["quality_evidence"] is False
    summary = write_closed_loop_comparison([report], tmp_path)
    assert "joint" in summary["missing_real_variants"]


def test_comparison_rejects_mixed_source_revisions_before_writing(
    reference: ClosedLoopReport,
    tmp_path: Path,
) -> None:
    different = run_closed_loop(
        ClosedLoopBaseline(), code_revision="different", measure_runtime=False
    )
    with pytest.raises(ValueError, match="same source revision"):
        write_closed_loop_comparison([reference, different], tmp_path / "unwritten")
    assert not (tmp_path / "unwritten").exists()
