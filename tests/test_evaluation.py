"""TTT-009 frozen benchmark, guard, baseline, and report tests."""

from __future__ import annotations

import pytest

from techrotic_training_triumvirate.evaluation import (
    EXPECTED_BENCHMARK_HASH,
    BenchmarkReport,
    CaseResult,
    FrozenEvaluationGuardError,
    ScriptedCommanderBaseline,
    WeakCommanderBaseline,
    frozen_evaluation_guard,
    load_benchmark_v1,
    run_benchmark,
)


def _section(report: BenchmarkReport, name: str) -> dict[str, object]:
    operational = report.operational
    section = operational[name]
    assert isinstance(section, dict)
    return section


def _case(report: BenchmarkReport, kind: str) -> CaseResult:
    return next(item for item in report.cases if item.kind == kind)


def test_frozen_manifest_is_integrity_checked_and_complete() -> None:
    manifest = load_benchmark_v1()
    assert manifest.manifest_hash == EXPECTED_BENCHMARK_HASH
    assert len(manifest.generated) == 3
    assert len(manifest.adversarial) == 10
    assert {case.kind for case in manifest.adversarial} == {
        "malformed_command",
        "capability_mismatch",
        "delayed_execution_failure",
        "stale_observation",
        "conflicting_orders",
        "changed_objective",
        "secret_leakage",
        "fabricated_results",
        "intercept_over_disclosure",
        "repetition_degeneration",
    }


def test_frozen_guard_blocks_training_and_corrective_reuse() -> None:
    manifest = load_benchmark_v1()
    guard = frozen_evaluation_guard()
    frozen = manifest.generated[0]

    assert guard.benchmark_hash == manifest.manifest_hash
    assert guard.is_reserved(family=frozen.family, seed=frozen.seed)
    with pytest.raises(FrozenEvaluationGuardError, match="reserved"):
        guard.assert_training_allowed(family=frozen.family, seed=frozen.seed)

    guard.assert_training_allowed(family=frozen.family, seed=frozen.seed + 999_999)


def test_scripted_baseline_report_is_byte_deterministic() -> None:
    first = run_benchmark(
        ScriptedCommanderBaseline(),
        code_revision="test-revision",
    )
    second = run_benchmark(
        ScriptedCommanderBaseline(),
        code_revision="test-revision",
    )

    assert first.to_json() == second.to_json()
    assert first.report_hash() == second.report_hash()
    assert first.benchmark_hash == EXPECTED_BENCHMARK_HASH
    assert "Operational competence" in first.to_markdown()
    assert "Character proxies" in first.to_markdown()


def test_competent_and_weak_baselines_have_meaningfully_different_scores() -> None:
    competent = run_benchmark(
        ScriptedCommanderBaseline(),
        code_revision="test-revision",
    )
    weak = run_benchmark(
        WeakCommanderBaseline(),
        code_revision="test-revision",
    )

    competent_mechanical = _section(competent, "mechanical")
    weak_mechanical = _section(weak, "mechanical")
    assert isinstance(competent_mechanical["score"], float)
    assert isinstance(weak_mechanical["score"], float)
    assert competent_mechanical["score"] > weak_mechanical["score"] + 0.15

    competent_closed = _section(competent, "closed_loop")
    weak_closed = _section(weak, "closed_loop")
    assert isinstance(competent_closed["score"], float)
    assert isinstance(weak_closed["score"], float)
    assert competent_closed["score"] > weak_closed["score"]


def test_deliberate_secret_leakage_and_fabricated_success_fail() -> None:
    competent = run_benchmark(
        ScriptedCommanderBaseline(),
        code_revision="test-revision",
    )
    weak = run_benchmark(
        WeakCommanderBaseline(),
        code_revision="test-revision",
    )

    competent_hidden = _section(competent, "hidden_information")
    weak_hidden = _section(weak, "hidden_information")
    assert competent_hidden["critical_violation_count"] == 0
    assert weak_hidden["secret_leakage_count"] > 0
    assert weak_hidden["fabricated_result_count"] > 0
    assert weak_hidden["critical_violation_count"] > 0
    assert weak_hidden["score"] == 0.0

    secret_case = _case(weak, "secret_leakage")
    fabricated_case = _case(weak, "fabricated_results")
    assert secret_case.violations["secret_leakage_count"] > 0
    assert fabricated_case.violations["fabricated_result_count"] > 0


def test_adversarial_recovery_and_intercept_grounding_are_scored() -> None:
    competent = run_benchmark(
        ScriptedCommanderBaseline(),
        code_revision="test-revision",
    )

    stale_case = _case(competent, "stale_observation")
    delayed_case = _case(competent, "delayed_execution_failure")
    intercept_case = _case(competent, "intercept_over_disclosure")

    assert stale_case.metrics["stale_recovery_rate"] == 1.0
    assert delayed_case.metrics["execution_failure_recovery_rate"] == 1.0
    assert intercept_case.violations["intercept_over_disclosure_count"] == 0
    assert intercept_case.violations["intercept_grounding_failure_count"] == 0


def test_benchmark_consumes_ttt005_deterministic_renderer_surface() -> None:
    delegate = ScriptedCommanderBaseline()

    class RenderingProbe:
        @property
        def identity(self):
            return delegate.identity

        def begin_case(self, *, case_id: str, seed: int) -> None:
            delegate.begin_case(case_id=case_id, seed=seed)

        def act(self, context):
            assert context.structured_observation == context.observation.to_dict()
            assert context.compact_observation.startswith(f"TURN {context.turn_index}")
            return delegate.act(context)

    report = run_benchmark(RenderingProbe(), code_revision="test-revision")
    assert report.cases


def test_report_keeps_character_proxies_separate_from_operational_scores() -> None:
    report = run_benchmark(
        ScriptedCommanderBaseline(),
        code_revision="test-revision",
    )

    assert set(report.operational) == {
        "mechanical",
        "closed_loop",
        "hidden_information",
    }
    assert set(report.character) == {
        "automated_proxies",
        "human_evaluation_required",
    }
    human = report.character["human_evaluation_required"]
    assert isinstance(human, list)
    assert "humour" in human
    assert "surprise" in human
    proxies = report.character["automated_proxies"]
    assert isinstance(proxies, dict)
    assert "constraint_adherence_rate" in proxies
    assert "repetition_rate" in proxies
    assert "lexical_diversity" in proxies
    assert "phrase_diversity" in proxies
    assert "doctrine_consistency_rate" in proxies
