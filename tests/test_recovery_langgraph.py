"""LangGraph integration and TTT-010 acceptance tests."""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from techrotic_training_triumvirate.evaluation import (  # noqa: E402
    FrozenEvaluationGuardError,
    PolicyIdentity,
)
from techrotic_training_triumvirate.recovery import (  # noqa: E402
    FailureCategory,
    RecoveryRunConfig,
    ReplayCorrectionAdapter,
    ScriptedStep,
    ScriptedStudentAdapter,
)
from techrotic_training_triumvirate.recovery.langgraph_runner import (  # noqa: E402
    run_corrective_round,
)
from techrotic_training_triumvirate.schemas import canonical_json  # noqa: E402
from techrotic_training_triumvirate.session.langgraph_backend import (  # noqa: E402
    LangGraphSession,
)
from techrotic_training_triumvirate.world import (  # noqa: E402
    ScenarioConfig,
    ScenarioGenerator,
)


def _student(*, malformed: bool = False) -> ScriptedStudentAdapter:
    command_body: dict[str, object]
    if malformed:
        command_body = {
            "op": "launch_shell",
            "script": "pretend-success",
        }
    else:
        command_body = {
            "op": "assign_objective",
            "unit_id": "unit-1",
            "objective_kind": "secure",
            "target_id": "relay-east",
            "approach": "direct",
            "constraints": [],
        }
    return ScriptedStudentAdapter(
        identity=PolicyIdentity(
            policy_id="ttt-010-error-prone",
            adapter_id="deterministic-script",
            revision="v1",
        ),
        steps=(ScriptedStep(command_body=command_body),),
    )


def _config(
    run_id: str,
    *,
    seed: int = 24301,
    alternatives: int = 1,
    iteration: int = 0,
    parent_run_id: str | None = None,
) -> RecoveryRunConfig:
    return RecoveryRunConfig(
        run_id=run_id,
        git_commit="test-revision",
        seed=seed,
        turns=1,
        iteration=iteration,
        parent_run_id=parent_run_id,
        alternatives_per_failure=alternatives,
        corpus_dev_percent=0,
    )


def test_error_prone_student_builds_t3_corpus_and_replay_policy_improves() -> None:
    student = _student()
    first = run_corrective_round(student, config=_config("round-1"))

    assert first.failure_count == 1
    assert first.corrections
    assert first.corpus.examples
    assert all(example.tier.value == "T3" for example in first.corpus.examples)
    assert all(example.mode == "recovery" for example in first.corpus.examples)

    replay = ReplayCorrectionAdapter.from_pairs(
        first.replay_pairs(),
        fallback=student,
        revision=first.manifest.content_hash(),
    )
    second = run_corrective_round(
        replay,
        config=_config(
            "round-2",
            iteration=1,
            parent_run_id="round-1",
        ),
    )

    assert second.failure_count < first.failure_count
    assert second.failure_count == 0
    assert second.manifest.parent_run_ids == ("round-1",)


def test_invalid_command_recovery_is_categorized_and_corrected() -> None:
    run = run_corrective_round(
        _student(malformed=True),
        config=_config("invalid-command"),
    )

    failure = run.corrections[0].failure
    assert failure.category is FailureCategory.COMMAND_SCHEMA
    assert failure.code == "SCHEMA_INVALID"
    assert run.corpus.examples
    assert run.corpus.examples[0].mode == "recovery"


def test_delayed_execution_failure_replans_from_historical_state() -> None:
    run = run_corrective_round(
        _student(),
        config=_config("delayed-route"),
    )

    assert run.failure_count == 1
    correction = run.corrections[0]
    assert correction.failure.category is FailureCategory.EXECUTION_ROUTE
    assert correction.failure.code == "ROUTE_BLOCKED"
    corrected_body = correction.corrected_action.commands[0].body
    assert corrected_body["approach"] == "north"
    assert correction.recording.parent_turn_id == 0
    assert correction.recording.parent_branch_id == "main"
    assert correction.recording.turns[0].observation == (
        run.original_recording.turns[0].observation
    )


def test_original_branch_is_preserved_and_multiple_correction_forks_survive() -> None:
    run = run_corrective_round(
        _student(),
        config=_config("multiple-forks", alternatives=2),
    )

    assert len(run.corrections) == 2
    assert {item.alternative_index for item in run.corrections} == {0, 1}
    assert len({item.branch_id for item in run.corrections}) == 2
    assert len({item.branch_checkpoint_id for item in run.corrections}) == 2

    for correction in run.corrections:
        assert correction.original_recording_hash == (
            run.original_recording.semantic_hash()
        )
        assert correction.recording.parent_branch_id == "main"
        assert correction.recording.parent_turn_id == 0
        assert correction.branch_checkpoint_id != correction.original_checkpoint_id


def test_corrected_branch_replay_has_same_ttt_semantic_hash() -> None:
    run = run_corrective_round(
        _student(),
        config=_config("branch-replay"),
    )
    correction = run.corrections[0]

    verifier = LangGraphSession()
    evidence = verifier.verify_recording(
        correction.recording,
        thread_id="branch-replay-verification",
    )

    assert evidence.semantic_hash == correction.recording.semantic_hash()
    assert evidence.final_world_hash == correction.recording.final_world_hash


def test_t3_input_never_contains_privileged_simulator_fields_or_lineage() -> None:
    run = run_corrective_round(
        _student(),
        config=_config(
            "hidden-state",
            iteration=3,
            parent_run_id="round-parent",
        ),
    )
    blueprint = ScenarioGenerator().generate(
        seed=24301,
        config=ScenarioConfig(),
    )
    private_values = {
        *blueprint.private_facts.keys(),
        *(
            value
            for value in blueprint.private_facts.values()
            if isinstance(value, str)
        ),
    }

    assert run.corpus.examples
    for example in run.corpus.examples:
        visible = canonical_json(example.input)
        assert all(value not in visible for value in private_values)
        assert "abstract-simulator-oracle-v1" not in visible
        assert "round-parent" not in visible
        assert "langgraph" not in visible.lower()

    source = run.corrections[0].corpus_source
    provenance = source.provenance[0]
    assert provenance.metadata["oracle_id"] == "abstract-simulator-oracle-v1"
    assert provenance.metadata["iteration"] == 3
    assert provenance.metadata["parent_round_run_id"] == "round-parent"
    assert provenance.metadata["parent_branch_id"] == "main"
    assert provenance.metadata["langgraph_checkpoint_ref"]


def test_same_semantic_correction_is_deterministic_despite_checkpoint_ids() -> None:
    first = run_corrective_round(
        _student(),
        config=_config("deterministic-correction"),
    )
    second = run_corrective_round(
        _student(),
        config=_config("deterministic-correction"),
    )

    assert first.corpus.manifest == second.corpus.manifest
    assert first.corpus.examples == second.corpus.examples
    assert (
        first.corrections[0].recording.semantic_hash()
        == second.corrections[0].recording.semantic_hash()
    )


def test_frozen_evaluation_world_is_refused_before_rollout_or_corpus_admission() -> None:
    with pytest.raises(FrozenEvaluationGuardError, match="reserved"):
        run_corrective_round(
            _student(),
            config=_config("frozen-refusal", seed=240901),
        )
