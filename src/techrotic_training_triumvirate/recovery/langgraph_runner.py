"""LangGraph-backed student-visited corrective rollout pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from techrotic_training_triumvirate.commands import CommandInterpreter
from techrotic_training_triumvirate.corpus import (
    CorpusBuild,
    CorpusConfig,
    CorpusSource,
    CorpusTier,
    RecoveryContext,
    assemble_corpus,
)
from techrotic_training_triumvirate.evaluation import (
    EvaluationContext,
    FrozenEvaluationGuardError,
    PolicyIdentity,
    StudentAdapter,
    frozen_evaluation_guard,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommanderObservation,
    CommanderPrivateContext,
    EpisodeRecord,
    EvaluationAnnotations,
    InterpreterResult,
    PersonaSpec,
    RunManifest,
    SchemaValidationError,
    SourceProvenance,
    TurnRecord,
    canonical_json,
    content_hash,
)
from techrotic_training_triumvirate.session import (
    DeterministicRenderer,
    SessionRecording,
    SessionRenderer,
)
from techrotic_training_triumvirate.session.langgraph_backend import (
    BranchResult,
    LangGraphSession,
)
from techrotic_training_triumvirate.world import (
    ScenarioConfig,
    ScenarioGenerator,
    WorldAuthority,
    WorldBlueprint,
)

from .model import FailureCategory, FailurePoint, RecoveryRunConfig
from .oracle import CorrectionOracle, DeterministicRecoveryOracle


@dataclass(frozen=True, slots=True)
class RolloutTurn:
    """Complete student-visible action plus authoritative turn evidence."""

    turn_id: int
    observation: CommanderObservation
    action: AssistantAction
    interpreter_results: tuple[InterpreterResult, ...]
    world_events: tuple[AuthoritativeEvent, ...]
    next_observation: CommanderObservation
    failures: tuple[FailurePoint, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "turn_id": self.turn_id,
            "observation": self.observation.to_dict(),
            "action": self.action.to_dict(),
            "interpreter_results": [
                result.to_dict() for result in self.interpreter_results
            ],
            "world_events": [event.to_dict() for event in self.world_events],
            "next_observation": self.next_observation.to_dict(),
            "failures": [failure.to_summary() for failure in self.failures],
        }


@dataclass(frozen=True, slots=True)
class CorrectionFork:
    """One accepted corrected continuation from a historical checkpoint."""

    failure: FailurePoint
    alternative_index: int
    corrected_action: AssistantAction
    recording: SessionRecording
    corpus_source: CorpusSource
    branch_id: str
    branch_checkpoint_id: str
    original_checkpoint_id: str
    original_recording_hash: str

    @property
    def observation_hash(self) -> str:
        turn_id = self.corpus_source.recovery_contexts[0].turn_id
        return self.corpus_source.episode.turns[turn_id].observation.content_hash()


@dataclass(frozen=True, slots=True)
class CorrectiveRun:
    """Complete deterministic TTT-010 round."""

    config: RecoveryRunConfig
    policy: PolicyIdentity
    rollout: tuple[RolloutTurn, ...]
    original_recording: SessionRecording
    corrections: tuple[CorrectionFork, ...]
    corpus: CorpusBuild
    manifest: RunManifest

    @property
    def failure_count(self) -> int:
        return sum(len(turn.failures) for turn in self.rollout)

    def replay_pairs(self) -> tuple[tuple[str, AssistantAction], ...]:
        ordered = sorted(
            self.corrections,
            key=lambda item: (
                item.failure.turn_id,
                item.failure.attempt_id,
                item.alternative_index,
            ),
        )
        return tuple(
            (item.observation_hash, item.corrected_action) for item in ordered
        )


_COMMAND_CATEGORIES: dict[str, FailureCategory] = {
    "SCHEMA_INVALID": FailureCategory.COMMAND_SCHEMA,
    "PROTOCOL_UNSUPPORTED": FailureCategory.COMMAND_PROTOCOL,
    "ENTITY_UNKNOWN": FailureCategory.COMMAND_ENTITY,
    "ENTITY_UNAVAILABLE": FailureCategory.COMMAND_ENTITY,
    "CAPABILITY_MISMATCH": FailureCategory.COMMAND_CAPABILITY,
    "TARGET_INVALID": FailureCategory.COMMAND_TARGET,
    "PRECONDITION_FAILED": FailureCategory.COMMAND_PRECONDITION,
    "RESOURCE_EXHAUSTED": FailureCategory.COMMAND_RESOURCE,
    "STALE_OBSERVATION": FailureCategory.COMMAND_STALE,
    "ORDER_CONFLICT": FailureCategory.COMMAND_CONFLICT,
}
_EXECUTION_CATEGORIES: dict[str, FailureCategory] = {
    "ROUTE_BLOCKED": FailureCategory.EXECUTION_ROUTE,
    "STALL_NO_PROGRESS": FailureCategory.EXECUTION_STALL,
    "RESOURCE_EXHAUSTED": FailureCategory.EXECUTION_RESOURCE,
    "TARGET_STATE_CHANGED": FailureCategory.EXECUTION_TARGET,
    "UNIT_LOST": FailureCategory.EXECUTION_UNIT_LOST,
}


def _persona() -> PersonaSpec:
    return PersonaSpec(
        persona_id="ttt-010-neutral-student",
        archetype="compact-commander",
        traits={"mode": "corrective-rollout"},
        speech_constraints=(),
        doctrine={},
        secret_ids=(),
        tactical_biases={},
    )


def _observation_generation(recording: SessionRecording) -> int:
    return recording.initial_world.generation + len(recording.turns)


def _current_observation(recording: SessionRecording) -> CommanderObservation:
    if recording.turns:
        return recording.turns[-1].next_observation
    return recording.initial_observation


def _evaluation_context(
    recording: SessionRecording,
    *,
    case_id: str,
    renderer: SessionRenderer,
    persona: PersonaSpec,
) -> EvaluationContext:
    observation = _current_observation(recording)
    previous_results = recording.turns[-1].results if recording.turns else ()
    recent_events = recording.turns[-1].events if recording.turns else ()
    turn_index = len(recording.turns)
    return EvaluationContext(
        case_id=case_id,
        turn_index=turn_index,
        observation_generation=_observation_generation(recording),
        observation=observation,
        structured_observation=renderer.structured_observation(observation),
        compact_observation=renderer.compact_observation(observation),
        previous_results=previous_results,
        recent_events=recent_events,
        persona=persona,
    )


def _failure_points(
    *,
    run_id: str,
    turn_id: int,
    observation: CommanderObservation,
    action: AssistantAction,
    results: tuple[InterpreterResult, ...],
    events: tuple[AuthoritativeEvent, ...],
) -> tuple[FailurePoint, ...]:
    if len(action.commands) != 1:
        raise ValueError(
            "TTT-010 session-v1 corrective rollout requires exactly one "
            "command per turn"
        )
    command_id = action.commands[0].command_id
    attempt_id = f"{run_id}:attempt:{turn_id:03d}"
    failures: list[FailurePoint] = []
    for result in results:
        if result.accepted:
            continue
        category = _COMMAND_CATEGORIES.get(
            result.code,
            FailureCategory.COMMAND_PRECONDITION,
        )
        failures.append(
            FailurePoint(
                turn_id=turn_id,
                attempt_id=attempt_id,
                command_id=command_id,
                category=category,
                code=result.code,
                observation=observation,
                action=action,
                interpreter_results=results,
                world_events=events,
            )
        )

    for event in events:
        if event.kind != "execution-failed":
            continue
        code_value = event.data.get("code")
        code = code_value if isinstance(code_value, str) else "EXECUTION_FAILED"
        failures.append(
            FailurePoint(
                turn_id=turn_id,
                attempt_id=attempt_id,
                command_id=command_id,
                category=_EXECUTION_CATEGORIES.get(
                    code,
                    FailureCategory.EXECUTION_OTHER,
                ),
                code=code,
                observation=observation,
                action=action,
                interpreter_results=results,
                world_events=events,
            )
        )
    return tuple(failures)


def _private_context(recording: SessionRecording) -> CommanderPrivateContext:
    return CommanderPrivateContext(
        commander_id="ttt-010-student",
        goals=tuple(recording.scenario.objective_ids),
        secret_ids=(),
        beliefs={},
        memory_refs=(),
    )


def _episode_from_recording(
    recording: SessionRecording,
    *,
    persona: PersonaSpec,
    episode_id: str,
    correction_turn_id: int,
) -> EpisodeRecord:
    blueprint = ScenarioGenerator().generate(
        seed=recording.seed,
        config=ScenarioConfig(mid_state=recording.mid_state),
    )
    if blueprint.scenario != recording.scenario:
        raise SchemaValidationError("corrected recording scenario regeneration drifted")
    world = WorldAuthority(blueprint)
    if world.world_private_reference() != recording.initial_world:
        raise SchemaValidationError("corrected recording initial world drifted")

    interpreter = CommandInterpreter()
    turns: list[TurnRecord] = []
    private_context = _private_context(recording)
    for session_turn in recording.turns:
        if len(session_turn.action.commands) != 1:
            raise SchemaValidationError(
                "TTT-010 materialization requires one command per session turn"
            )
        observation = world.commander_observation(turn_id=session_turn.turn_id)
        if observation != session_turn.observation:
            raise SchemaValidationError("corrected branch observation drifted")
        player_observation = world.player_observation(turn_id=session_turn.turn_id)
        before_events = len(world.events)
        outcome = interpreter.interpret(session_turn.action.commands[0], world)
        if outcome.dispatch_event is not None:
            world.events.append(outcome.dispatch_event)
        world.step()
        events = tuple(world.events[before_events:])
        next_observation = world.commander_observation(
            turn_id=session_turn.turn_id + 1
        )
        if (outcome.result,) != session_turn.results:
            raise SchemaValidationError("corrected branch interpreter result drifted")
        if events != session_turn.events:
            raise SchemaValidationError("corrected branch event sequence drifted")
        if next_observation != session_turn.next_observation:
            raise SchemaValidationError("corrected branch next observation drifted")
        turns.append(
            TurnRecord(
                turn_id=session_turn.turn_id,
                observation=session_turn.observation,
                commander_private_context=private_context,
                assistant_action=session_turn.action,
                interpreter_results=session_turn.results,
                world_events=session_turn.events,
                next_observation=session_turn.next_observation,
                player_observation=player_observation,
                player_intercepts=(),
                annotations=EvaluationAnnotations(
                    labels={
                        "t3_correction": session_turn.turn_id == correction_turn_id
                    },
                    evaluator_only={},
                ),
            )
        )

    if world.state_hash() != recording.final_world_hash:
        raise SchemaValidationError("corrected branch final world hash drifted")
    return EpisodeRecord(
        episode_id=episode_id,
        scenario=recording.scenario,
        persona=persona,
        initial_world=recording.initial_world,
        turns=tuple(turns),
        final_world_hash=recording.final_world_hash,
        run_id=recording.run_id,
    )


def _correction_is_admissible(branch: BranchResult) -> bool:
    if not branch.recording.turns:
        return False
    turn = branch.recording.turns[-1]
    if not turn.results or any(not result.accepted for result in turn.results):
        return False
    return not any(event.kind == "execution-failed" for event in turn.events)


def _provenance(
    *,
    config: RecoveryRunConfig,
    policy: PolicyIdentity,
    oracle: CorrectionOracle,
    failure: FailurePoint,
    alternative_index: int,
    branch: BranchResult,
) -> SourceProvenance:
    branch_recording = branch.recording
    source_id = (
        f"t3:{config.run_id}:{failure.turn_id:03d}:{alternative_index:02d}"
    )
    semantic_source_hash = content_hash(
        {
            "recording_hash": branch_recording.semantic_hash(),
            "failure": failure.to_summary(),
            "oracle_id": oracle.oracle_id,
            "alternative_index": alternative_index,
        }
    )
    return SourceProvenance(
        source_id=source_id,
        source_class="student-generated-rollout",
        uri=None,
        revision=config.git_commit,
        license_id=None,
        source_content_hash=semantic_source_hash,
        metadata={
            "tier": "T3",
            "student_policy": {
                "policy_id": policy.policy_id,
                "adapter_id": policy.adapter_id,
                "revision": policy.revision,
            },
            "oracle_id": oracle.oracle_id,
            "failure_category": failure.category.value,
            "failure_code": failure.code,
            "iteration": config.iteration,
            "parent_round_run_id": config.parent_run_id,
            "parent_branch_id": branch_recording.parent_branch_id,
            "parent_turn_hash": branch_recording.parent_turn_hash,
            "langgraph_checkpoint_ref": branch.branch_checkpoint_id,
        },
    )


def _private_strings(blueprint: WorldBlueprint) -> tuple[str, ...]:
    values = [
        value
        for value in blueprint.private_facts.values()
        if isinstance(value, str) and value
    ]
    return tuple(sorted({*blueprint.private_facts.keys(), *values}))


def _assert_no_private_leak(build: CorpusBuild, blueprint: WorldBlueprint) -> None:
    forbidden = _private_strings(blueprint)
    for example in build.examples:
        surface = canonical_json(example.input)
        leaked = tuple(value for value in forbidden if value in surface)
        if leaked:
            raise SchemaValidationError(
                "T3 model-visible input contains privileged simulator fields: "
                f"{leaked!r}"
            )


def run_corrective_round(
    adapter: StudentAdapter,
    *,
    config: RecoveryRunConfig,
    oracle: CorrectionOracle | None = None,
    renderer: SessionRenderer | None = None,
) -> CorrectiveRun:
    """Run one bounded student rollout and assemble validated T3 corrections."""

    resolved_oracle = oracle or DeterministicRecoveryOracle()
    resolved_renderer = renderer or DeterministicRenderer()
    persona = _persona()
    blueprint = ScenarioGenerator().generate(
        seed=config.seed,
        config=ScenarioConfig(mid_state=config.mid_state),
    )
    guard = frozen_evaluation_guard()
    guard.assert_training_allowed(
        family=blueprint.scenario.identity.family,
        seed=blueprint.scenario.identity.seed,
    )

    base = SessionRecording.new(
        session_id=f"{config.run_id}:session",
        run_id=config.run_id,
        seed=config.seed,
        mid_state=config.mid_state,
    )
    if base.scenario != blueprint.scenario:
        raise SchemaValidationError("rollout scenario does not match session scenario")

    graph = LangGraphSession()
    thread_id = f"{config.run_id}:original"
    recording = base
    rollout: list[RolloutTurn] = []
    failures: list[FailurePoint] = []
    adapter.begin_case(case_id=config.run_id, seed=config.seed)

    for _ in range(config.turns):
        context = _evaluation_context(
            recording,
            case_id=config.run_id,
            renderer=resolved_renderer,
            persona=persona,
        )
        action = adapter.act(context)
        if len(action.commands) != 1:
            raise ValueError(
                "TTT-010 session-v1 corrective rollout requires exactly one "
                "command per turn"
            )
        updated = graph.run_commands(
            recording,
            (action.commands[0],),
            thread_id=thread_id,
        )
        session_turn = updated.turns[-1]
        turn_failures = _failure_points(
            run_id=config.run_id,
            turn_id=session_turn.turn_id,
            observation=session_turn.observation,
            action=action,
            results=session_turn.results,
            events=session_turn.events,
        )
        failures.extend(turn_failures)
        rollout.append(
            RolloutTurn(
                turn_id=session_turn.turn_id,
                observation=session_turn.observation,
                action=action,
                interpreter_results=session_turn.results,
                world_events=session_turn.events,
                next_observation=session_turn.next_observation,
                failures=turn_failures,
            )
        )
        recording = updated

    corrections: list[CorrectionFork] = []
    sources: list[CorpusSource] = []
    for failure in failures:
        generation = base.initial_world.generation + failure.turn_id
        proposals = resolved_oracle.propose(
            failure,
            observation_generation=generation,
            blueprint=blueprint,
            max_alternatives=config.alternatives_per_failure,
        )
        for alternative_index, corrected_action in enumerate(proposals):
            if len(corrected_action.commands) != 1:
                continue
            branch_id = (
                f"{config.run_id}:correction:{failure.turn_id:03d}:"
                f"{alternative_index:02d}"
            )
            branch = graph.branch_correction(
                thread_id=thread_id,
                original_command_id=failure.command_id,
                corrected_command=corrected_action.commands[0],
                branch_id=branch_id,
            )
            if not _correction_is_admissible(branch):
                continue
            correction_turn_id = len(branch.recording.turns) - 1
            parent_branch_id = branch.recording.parent_branch_id
            parent_turn_hash = branch.recording.parent_turn_hash
            if parent_branch_id is None or parent_turn_hash is None:
                raise SchemaValidationError(
                    "corrected branch is missing TTT parent provenance"
                )
            recovery_context = RecoveryContext(
                turn_id=correction_turn_id,
                attempt_id=failure.attempt_id,
                prior_action=failure.action,
                interpreter_results=failure.interpreter_results,
                world_events=failure.world_events,
                oracle_id=resolved_oracle.oracle_id,
                parent_run_id=config.run_id,
                parent_branch_id=parent_branch_id,
                parent_turn_hash=parent_turn_hash,
            )
            provenance = _provenance(
                config=config,
                policy=adapter.identity,
                oracle=resolved_oracle,
                failure=failure,
                alternative_index=alternative_index,
                branch=branch,
            )
            episode = _episode_from_recording(
                branch.recording,
                persona=persona,
                episode_id=f"{config.run_id}:episode:{branch_id}",
                correction_turn_id=correction_turn_id,
            )
            source = CorpusSource(
                episode=episode,
                tier=CorpusTier.T3,
                provenance=(provenance,),
                recovery_contexts=(recovery_context,),
            )
            fork = CorrectionFork(
                failure=failure,
                alternative_index=alternative_index,
                corrected_action=corrected_action,
                recording=branch.recording,
                corpus_source=source,
                branch_id=branch_id,
                branch_checkpoint_id=branch.branch_checkpoint_id,
                original_checkpoint_id=branch.original_checkpoint_id,
                original_recording_hash=branch.original_recording_hash,
            )
            corrections.append(fork)
            sources.append(source)

    corpus = assemble_corpus(
        tuple(sources),
        config=CorpusConfig(
            seed=config.seed,
            dev_percent=config.corpus_dev_percent,
        ),
    )
    if corpus.quarantine:
        details = tuple(
            (item.episode_id, tuple(issue.code for issue in item.issues))
            for item in corpus.quarantine
        )
        raise SchemaValidationError(
            f"TTT-010 corpus validation refused sources: {details}"
        )
    _assert_no_private_leak(corpus, blueprint)

    source_refs = tuple(
        sorted(
            provenance.source_id
            for source in sources
            for provenance in source.provenance
        )
    )
    manifest = RunManifest(
        run_id=config.run_id,
        git_commit=config.git_commit,
        schema_versions={
            "ttt.episode": 1,
            "ttt.source_provenance": 1,
            "ttt.session_recording": 1,
        },
        seeds={"scenario": config.seed},
        generator_config={
            "kind": "student-visited-corrective",
            "iteration": config.iteration,
            "turns": config.turns,
            "alternatives_per_failure": config.alternatives_per_failure,
            "student_policy_id": adapter.identity.policy_id,
            "student_adapter_id": adapter.identity.adapter_id,
            "student_revision": adapter.identity.revision,
            "oracle_id": resolved_oracle.oracle_id,
        },
        source_refs=source_refs,
        parent_run_ids=(
            (config.parent_run_id,) if config.parent_run_id is not None else ()
        ),
        artifact_hashes={
            "original_session": recording.semantic_hash(),
            "student_rollout": content_hash([turn.to_dict() for turn in rollout]),
            "corpus_manifest": content_hash(corpus.manifest),
            "correction_recordings": content_hash(
                [item.recording.semantic_hash() for item in corrections]
            ),
        },
        command_line=("ttt-010", "corrective-rollout"),
        runtime={
            "orchestration": "langgraph",
            "live_llm": False,
            "student_policy": adapter.identity.policy_id,
        },
    )
    return CorrectiveRun(
        config=config,
        policy=adapter.identity,
        rollout=tuple(rollout),
        original_recording=recording,
        corrections=tuple(corrections),
        corpus=corpus,
        manifest=manifest,
    )


__all__ = [
    "CorrectionFork",
    "CorrectiveRun",
    "FrozenEvaluationGuardError",
    "RolloutTurn",
    "run_corrective_round",
]
