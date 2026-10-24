"""Dependency-light TTT-010 adapter and corpus-boundary tests."""

from __future__ import annotations

from techrotic_training_triumvirate.commands import AssignObjectiveCommand
from techrotic_training_triumvirate.corpus import (
    CorpusConfig,
    CorpusSource,
    CorpusTier,
    RecoveryContext,
    assemble_corpus,
)
from techrotic_training_triumvirate.evaluation import EvaluationContext, PolicyIdentity
from techrotic_training_triumvirate.recovery import (
    ReplayCorrectionAdapter,
    ScriptedStep,
    ScriptedStudentAdapter,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    PersonaSpec,
    canonical_json,
)
from techrotic_training_triumvirate.schemas.fixtures import (
    t0_episode,
    t0_normal_turn,
    t0_recovery_turn,
    t0_source_provenance,
)
from techrotic_training_triumvirate.session import (
    DeterministicRenderer,
    SessionRecording,
)


def _persona() -> PersonaSpec:
    return PersonaSpec(
        persona_id="recovery-test-persona",
        archetype="tester",
        traits={},
        speech_constraints=(),
        doctrine={},
        secret_ids=(),
        tactical_biases={},
    )


def _context(*, generation: int = 0) -> EvaluationContext:
    recording = SessionRecording.new(
        session_id="adapter-test-session",
        run_id="adapter-test-run",
        seed=24301,
    )
    observation = recording.initial_observation
    renderer = DeterministicRenderer()
    return EvaluationContext(
        case_id="adapter-test",
        turn_index=0,
        observation_generation=generation,
        observation=observation,
        structured_observation=renderer.structured_observation(observation),
        compact_observation=renderer.compact_observation(observation),
        previous_results=(),
        recent_events=(),
        persona=_persona(),
    )


def _direct_student() -> ScriptedStudentAdapter:
    return ScriptedStudentAdapter(
        identity=PolicyIdentity(
            policy_id="error-prone-script",
            adapter_id="ttt-010-scripted",
            revision="test-v1",
        ),
        steps=(
            ScriptedStep(
                command_body={
                    "op": "assign_objective",
                    "unit_id": "unit-1",
                    "objective_kind": "secure",
                    "target_id": "relay-east",
                    "approach": "direct",
                    "constraints": [],
                },
                communication_text="Take the direct route.",
            ),
        ),
    )


def test_scripted_student_is_deterministic_and_binds_current_generation() -> None:
    adapter = _direct_student()
    context = _context(generation=7)

    first = adapter.act(context)
    second = adapter.act(context)

    assert first == second
    assert first.commands[0].body["observation_generation"] == 7
    assert first.communications[0].text == "Take the direct route."


def test_replay_adapter_uses_correction_for_exact_observation_hash() -> None:
    context = _context(generation=5)
    corrected = AssistantAction(
        commands=(
            AssignObjectiveCommand(
                command_id="old-correction-id",
                observation_generation=0,
                unit_id="unit-1",
                objective_kind="secure",
                target_id="relay-east",
                approach="north",
                constraints=(),
            ).to_envelope(),
        ),
        communications=(),
    )
    replay = ReplayCorrectionAdapter.from_pairs(
        ((context.observation.content_hash(), corrected),),
        fallback=_direct_student(),
        revision="replay-test-v1",
    )

    action = replay.act(context)

    assert action.commands[0].body["approach"] == "north"
    assert action.commands[0].body["observation_generation"] == 5
    assert action.commands[0].command_id != "old-correction-id"


def test_external_t3_recovery_context_routes_through_corpus_validation() -> None:
    failed = t0_recovery_turn()
    source = CorpusSource(
        episode=t0_episode(),
        tier=CorpusTier.T3,
        provenance=(t0_source_provenance(),),
        recovery_contexts=(
            RecoveryContext(
                turn_id=0,
                attempt_id="attempt-0001",
                prior_action=failed.assistant_action,
                interpreter_results=failed.interpreter_results,
                world_events=failed.world_events,
                oracle_id="oracle-test-v1",
                parent_run_id="student-run-1",
                parent_branch_id="main",
                parent_turn_hash="a" * 64,
            ),
        ),
    )

    build = assemble_corpus(
        (source,),
        config=CorpusConfig(seed=3, dev_percent=0),
    )

    assert not build.quarantine
    assert len(build.examples) == 1
    example = build.examples[0]
    assert example.tier is CorpusTier.T3
    assert example.mode == "recovery"
    assert example.turn_id == 0
    prior_failure = example.input["prior_failure"]
    assert isinstance(prior_failure, dict)
    visible = canonical_json(prior_failure)
    assert "PRECONDITION_FAILED" not in visible
    assert "ROUTE_BLOCKED" in visible
    assert "oracle-test-v1" not in visible
    assert "student-run-1" not in visible
    assert "main" not in visible
    target = canonical_json(example.target)
    assert "interpreter_results" not in target
    assert "world_events" not in target


def test_external_recovery_without_authoritative_failure_is_quarantined() -> None:
    accepted = t0_normal_turn()
    source = CorpusSource(
        episode=t0_episode(),
        tier=CorpusTier.T3,
        provenance=(t0_source_provenance(),),
        recovery_contexts=(
            RecoveryContext(
                turn_id=0,
                attempt_id="attempt-invalid",
                prior_action=accepted.assistant_action,
                interpreter_results=accepted.interpreter_results,
                world_events=accepted.world_events,
                oracle_id="oracle-test-v1",
                parent_run_id="student-run-invalid",
                parent_branch_id="main",
                parent_turn_hash="b" * 64,
            ),
        ),
    )

    build = assemble_corpus((source,), config=CorpusConfig(dev_percent=0))

    assert not build.examples
    assert build.quarantine
    assert {issue.code for item in build.quarantine for issue in item.issues} == {
        "RECOVERY_MALFORMED"
    }
