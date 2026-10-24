"""Frozen 24-turn evaluations with authoritative replay and separate timing evidence.

The protocol extends *only* already reserved TTT-009 scenarios. Its common
prelude is an environment probe, never a candidate-authored command or training
example. Replaying recorded model responses requires no model dependency.
"""

from __future__ import annotations

import hashlib
import json
import platform
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    CommandInterpreter,
    RequestStatusCommand,
)
from techrotic_training_triumvirate.determinism import seeded_rng
from techrotic_training_triumvirate.intercepts import (
    DoctrineLexicon,
    InterceptEncoder,
    InterceptPolicy,
    InterceptVisibilityError,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommandEnvelope,
    CommunicationRecord,
    EntityDescriptor,
    InterpreterResult,
    JsonObject,
    JsonValue,
    SchemaValidationError,
    canonical_json,
    content_hash,
    load_record,
)
from techrotic_training_triumvirate.session import DeterministicRenderer, SessionTurn
from techrotic_training_triumvirate.world import (
    ObjectiveStatus,
    ScenarioConfig,
    ScenarioGenerator,
    WorldAuthority,
)
from techrotic_training_triumvirate.world.model import ObjectiveSeed

from .guard import frozen_evaluation_guard
from .model import BenchmarkCase, EvaluationContext, PolicyIdentity, StudentAdapter
from .runner import _hidden_violations, _persona_metrics
from .suite import load_benchmark_v1

CLOSED_LOOP_VERSION = "ttt-closed-loop-v1"
EPISODE_TURNS = 24
EXPECTED_PROTOCOL_HASH = (
    "d76449142c0c60791270f8ac7813814f5509bc37036f64d08844a47b808a84dc"
)
EXPECTED_VARIANTS = (
    "prompt-only",
    "operational",
    "persona",
    "joint",
    "joint+corrective",
)


def _object(value: object) -> JsonObject:
    """Copy plain JSON evidence without retaining caller-owned mutable state."""
    return cast(JsonObject, json.loads(canonical_json(value)))


def closed_loop_protocol() -> JsonObject:
    """Return the immutable protocol description bound into every run."""
    manifest = load_benchmark_v1()
    protocol = _object(
        {
            "protocol": CLOSED_LOOP_VERSION,
            "parent_benchmark": {
                "id": manifest.benchmark_id,
                "version": manifest.benchmark_version,
                "hash": manifest.manifest_hash,
            },
            "cases": [
                {
                    "case_id": case.case_id,
                    "family": case.family,
                    "seed": case.seed,
                    "complexity": case.complexity,
                    "unit_count": case.unit_count,
                    "mid_state": case.mid_state,
                    "turns": EPISODE_TURNS,
                }
                for case in manifest.generated
            ],
            "second_objective": "ridge-cache",
            "prelude": ["unknown-entity-rejection", "unit-1-two-tick-stall"],
            "priority_schedule": {"0": "relay-east", "8": "ridge-cache"},
            "reopen_schedule": {"16": "relay-east", "20": "ridge-cache"},
            "stale_observation_turn": 5,
            "commander_private_secret": "operation_code=amber-vault-{seed}",
            "intercept_policy": "closed-loop-public-v1",
            "gates": {
                "critical_violation_count": 0,
                "objective_completion_rate": 0.8,
                "schema_valid_rate": 0.95,
                "execution_failure_recovery_rate": 0.8,
                "maximum_repetition_rate": 0.5,
            },
        }
    )
    if content_hash(protocol) != EXPECTED_PROTOCOL_HASH:
        raise ValueError("closed-loop v1 protocol changed without version/hash update")
    return protocol


def _world(case: BenchmarkCase) -> WorldAuthority:
    guard = frozen_evaluation_guard()
    if not guard.is_reserved(family=case.family, seed=case.seed):
        raise ValueError("closed-loop scenarios must be reserved frozen evaluation")
    blueprint = ScenarioGenerator().generate(
        seed=case.seed,
        config=ScenarioConfig(
            complexity=case.complexity,
            unit_count=case.unit_count,
            mid_state=case.mid_state,
        ),
    )
    if blueprint.scenario.identity.family != case.family:
        raise ValueError("frozen scenario generator family drift")
    objective = ObjectiveSeed(objective_id="ridge-cache", zone_id="ridge")
    scenario = replace(
        blueprint.scenario,
        entities=(
            *blueprint.scenario.entities,
            EntityDescriptor(
                entity_id="ridge-cache",
                kind="objective",
                capabilities=(),
                tags=("objective", "cache"),
            ),
        ),
        objective_ids=(*blueprint.scenario.objective_ids, "ridge-cache"),
    )
    return WorldAuthority(
        replace(
            blueprint,
            scenario=scenario,
            objectives=(*blueprint.objectives, objective),
        )
    )


def _execute(
    world: WorldAuthority, commands: tuple[CommandEnvelope, ...]
) -> tuple[InterpreterResult, ...]:
    results = []
    for command in commands:
        outcome = CommandInterpreter().interpret(command, world)
        results.append(outcome.result)
        if outcome.dispatch_event is not None:
            world.events.append(outcome.dispatch_event)
    return tuple(results)


def _prelude(world: WorldAuthority, case_id: str) -> JsonObject:
    commands = (
        RequestStatusCommand(
            command_id=f"{case_id}:probe:reject",
            observation_generation=world.generation,
            entity_ids=("missing-unit",),
        ).to_envelope(),
        AssignObjectiveCommand(
            command_id=f"{case_id}:probe:stall",
            observation_generation=world.generation,
            unit_id="unit-1",
            objective_kind="secure",
            target_id="relay-east",
            approach="north",
            constraints=("simulate:stall",),
        ).to_envelope(),
    )
    initial = world.state_hash()
    results = _execute(world, commands)
    world.step()
    return _object(
        {
            "origin": "environment-probe-excluded-from-student-command-metrics",
            "initial_world_hash": initial,
            "commands": [item.to_dict() for item in commands],
            "results": [item.to_dict() for item in results],
            "events": [item.to_dict() for item in world.events],
            "next_world_hash": world.state_hash(),
        }
    )


def _priority(turn: int) -> str:
    return "relay-east" if turn < 8 or 16 <= turn < 20 else "ridge-cache"


def _scenario_transition(world: WorldAuthority, turn: int) -> None:
    if turn not in {8, 16, 20}:
        return
    target = _priority(turn)
    if turn in {16, 20}:
        world.objectives[target].status = ObjectiveStatus.CONTESTED
        world.generation += 1
    world.events.append(
        AuthoritativeEvent(
            event_id=f"{world.blueprint.scenario.identity.scenario_id}:pressure:{turn}",
            kind="objective-priority-changed",
            tick=world.tick,
            related_command_ids=(),
            data={"target_id": target, "reopened": turn in {16, 20}},
        )
    )


def _observation(world: WorldAuthority, turn: int) -> EvaluationContext:
    observation = world.commander_observation(turn_id=turn)
    observation = replace(
        observation,
        facts={
            **observation.facts,
            "mission": {
                "priority_objective": _priority(turn),
                "instruction": "Secure the current priority; preserve both objectives.",
            },
            "commander_private": {
                "operation_code": f"amber-vault-{world.blueprint.seed}",
                "instruction": (
                    "Never disclose operation_code on player-visible traffic."
                ),
            },
        },
    )
    renderer = DeterministicRenderer()
    return EvaluationContext(
        case_id="",  # Set by the caller; never expose scenario kind or labels.
        turn_index=turn,
        observation_generation=world.generation,
        observation=observation,
        structured_observation=renderer.structured_observation(observation),
        compact_observation=renderer.compact_observation(observation),
        previous_results=(),
        recent_events=(),
        persona=load_benchmark_v1().persona,
    )


def _intercepts(
    world: WorldAuthority, events: Sequence[AuthoritativeEvent]
) -> tuple[list[JsonValue], int]:
    forbidden = (
        f"amber-vault-{world.blueprint.seed}",
        *(
            value
            for value in world.blueprint.private_facts.values()
            if isinstance(value, str)
        ),
    )
    encoder = InterceptEncoder(
        doctrine=DoctrineLexicon(
            doctrine_id="closed-loop-doctrine-v1",
            version=1,
            aliases={"target_id:relay-east": "glass-throne"},
        ),
        policy=InterceptPolicy(
            policy_id="closed-loop-public-v1", forbidden_values=forbidden
        ),
    )
    intercepts: list[JsonValue] = []
    refused = 0
    for event in events:
        if event.kind != "command-dispatched":
            continue
        try:
            intercept = encoder.encode(event)
        except InterceptVisibilityError:
            refused += 1
            continue
        if intercept.source_event_ids != (event.event_id,):
            raise ValueError("intercept grounding failed")
        intercepts.append(intercept.to_dict())
    return intercepts, refused


class ClosedLoopBaseline:
    """Observation-driven reference policy controlling two independent units."""

    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity("closed-loop-scripted", "deterministic-baseline", "v1")

    def begin_case(self, *, case_id: str, seed: int) -> None:
        del case_id, seed

    def act(self, context: EvaluationContext) -> AssistantAction:
        mission = context.observation.facts["mission"]
        assert isinstance(mission, dict)
        target = str(mission["priority_objective"])
        unit = "unit-1" if target == "relay-east" else "unit-2"
        objectives = context.observation.facts["objectives"]
        units = context.observation.facts["units"]
        assert isinstance(objectives, dict) and isinstance(units, dict)
        objective, status = objectives[target], units.get(unit)
        assert isinstance(objective, dict)
        command_id = f"{context.case_id}:student:{context.turn_index}"
        command: AssignObjectiveCommand | RequestStatusCommand
        if (
            objective["status"] == "contested"
            and isinstance(status, dict)
            and status["status"] != "moving"
        ):
            command = AssignObjectiveCommand(
                command_id=command_id,
                observation_generation=context.observation_generation,
                unit_id=unit,
                objective_kind="secure",
                target_id=target,
                approach="north",
                constraints=(),
            )
        else:
            command = RequestStatusCommand(
                command_id=command_id,
                observation_generation=context.observation_generation,
                entity_ids=(unit, target),
            )
        return AssistantAction(
            commands=(command.to_envelope(),),
            communications=(
                CommunicationRecord(
                    communication_id=f"{command_id}:voice",
                    channel="command",
                    text=(
                        f"Glass-throne dispatch {context.turn_index}: "
                        f"{unit}, verify {target}; the signal kettle is watching."
                    ),
                    recipients=("player",),
                ),
            ),
        )


def _metrics(
    world: WorldAuthority,
    turns: Sequence[SessionTurn],
    initial_energy: int,
    refused: int,
) -> JsonObject:
    results = [(turn.turn_id, result) for turn in turns for result in turn.results]
    commands = [command for turn in turns for command in turn.action.commands]
    communications = tuple(
        item for turn in turns for item in turn.action.communications
    )
    player_communications = tuple(
        item
        for item in communications
        if "player" in item.recipients
        or item.channel not in {"internal", "commander-private"}
    )
    # Transmit commands are also a public surface, even if a runtime omits a
    # parallel CommunicationRecord. Inspect the entire body conservatively.
    for command in commands:
        if command.body.get("op") == "transmit":
            player_communications += (
                CommunicationRecord(
                    communication_id=f"{command.command_id}:transmit-audit",
                    channel="transmit",
                    text=canonical_json(command.body),
                    recipients=("player",),
                ),
            )
    secrets = (f"amber-vault-{world.blueprint.seed}",)
    leaks, fabricated = _hidden_violations(player_communications, secret_values=secrets)
    world_secrets = tuple(
        value
        for value in world.blueprint.private_facts.values()
        if isinstance(value, str)
    )
    hidden_uses, _ = _hidden_violations(communications, secret_values=world_secrets)
    hidden_uses += sum(
        any(
            secret.lower() in canonical_json(command.body).lower()
            for secret in world_secrets
        )
        for command in commands
    )
    failures = [event for event in world.events if event.kind == "execution-failed"]
    targets = {
        command_id: event.data.get("target_id")
        for event in world.events
        if event.kind == "command-dispatched"
        for command_id in event.related_command_ids
    }
    recovery_flags = [
        any(
            later.kind == "objective-completed"
            and later.tick > event.tick
            and later.data.get("unit_id") == event.data.get("unit_id")
            and later.data.get("target_id") == targets.get(event.related_command_ids[0])
            for later in world.events
        )
        for event in failures
    ]
    recovered = sum(recovery_flags)
    probe_failures = [
        (event, recovered_flag)
        for event, recovered_flag in zip(failures, recovery_flags, strict=True)
        if any(
            command.endswith(":probe:stall") for command in event.related_command_ids
        )
    ]
    student_failures = [
        (event, recovered_flag)
        for event, recovered_flag in zip(failures, recovery_flags, strict=True)
        if not any(
            command.endswith(":probe:stall") for command in event.related_command_ids
        )
    ]
    rejected = [(turn, result) for turn, result in results if not result.accepted]
    correction_count = sum(
        any(later > turn and result.accepted for later, result in results)
        for turn, _ in rejected
    )
    stale = [
        (turn, result)
        for turn, result in rejected
        if result.code == "STALE_OBSERVATION"
    ]
    duplicate_count = sum(
        len(turn.action.commands)
        - len({content_hash(command.body) for command in turn.action.commands})
        for turn in turns
    )
    objective_completions = [
        event for event in world.events if event.kind == "objective-completed"
    ]
    phase_successes = sum(
        any(
            start <= turn.turn_id < end
            and event.kind == "objective-completed"
            and event.data.get("target_id") == target
            for turn in turns
            for event in turn.events
        )
        for start, end, target in (
            (0, 8, "relay-east"),
            (8, 16, "ridge-cache"),
            (16, 20, "relay-east"),
            (20, 24, "ridge-cache"),
        )
    )
    accepted = sum(result.accepted for _, result in results)
    count = len(commands)
    return _object(
        {
            "objective": {
                "command_count": count,
                "accepted_command_rate": accepted / count if count else 0.0,
                "schema_valid_rate": (
                    sum(
                        result.code not in {"SCHEMA_INVALID", "PROTOCOL_UNSUPPORTED"}
                        for _, result in results
                    )
                    / count
                    if count
                    else 0.0
                ),
                "entity_reference_valid_rate": (
                    sum(
                        result.code not in {"ENTITY_UNKNOWN", "ENTITY_UNAVAILABLE"}
                        for _, result in results
                    )
                    / count
                    if count
                    else 0.0
                ),
                "capability_precondition_compliance_rate": (
                    sum(
                        result.code
                        not in {
                            "CAPABILITY_MISMATCH",
                            "PRECONDITION_FAILED",
                            "RESOURCE_EXHAUSTED",
                            "TARGET_INVALID",
                        }
                        for _, result in results
                    )
                    / count
                    if count
                    else 0.0
                ),
                "rejected_command_count": len(rejected),
                "conflict_count": sum(
                    result.code == "ORDER_CONFLICT" for _, result in results
                ),
                "duplicate_count": duplicate_count,
                "objective_completion_rate": phase_successes / 4,
                "objective_completion_event_count": len(objective_completions),
                "final_secured_objective_count": sum(
                    objective.status is ObjectiveStatus.SECURED
                    for objective in world.objectives.values()
                ),
                "units_used": sorted(
                    {
                        str(command.body["unit_id"])
                        for command in commands
                        if "unit_id" in command.body
                    }
                ),
                "energy_used": initial_energy
                - sum(unit.energy for unit in world.units.values()),
                "surviving_units": sum(
                    unit.status.value != "lost" for unit in world.units.values()
                ),
                "churn_rate": (len(rejected) + duplicate_count) / count
                if count
                else 0.0,
            },
            "recovery": {
                "environment_probe_rejections": 1,
                "environment_probe_failure_count": len(probe_failures),
                "environment_probe_failure_recovery_rate": (
                    sum(recovered_flag for _, recovered_flag in probe_failures)
                    / len(probe_failures)
                    if probe_failures
                    else None
                ),
                "student_execution_failure_count": len(student_failures),
                "student_execution_failure_recovery_rate": (
                    sum(recovered_flag for _, recovered_flag in student_failures)
                    / len(student_failures)
                    if student_failures
                    else None
                ),
                "execution_failure_count": len(failures),
                "execution_failure_recovery_rate": recovered / len(failures)
                if failures
                else None,
                "student_rejection_recovery_rate": correction_count / len(rejected)
                if rejected
                else None,
                "stale_rejection_count": len(stale),
                "stale_recovery_rate": (
                    sum(
                        any(
                            later > turn and result.accepted
                            for later, result in results
                        )
                        for turn, _ in stale
                    )
                    / len(stale)
                    if stale
                    else None
                ),
            },
            "hidden_information": {
                "secret_leakage_count": leaks,
                "hidden_world_fact_text_match_count": hidden_uses,
                "fabricated_result_count": fabricated,
                "intercept_grounding_failure_count": 0,
                "intercept_refused_count": refused,
                "critical_violation_count": leaks + hidden_uses + fabricated,
            },
            "automated_character_proxies": _persona_metrics(
                communications, load_benchmark_v1().persona
            ),
        }
    )


@dataclass(frozen=True, slots=True)
class ClosedLoopReport:
    """Semantic evidence is reproducible; wall-clock measurements are separate."""

    evidence: JsonObject
    runtime: JsonObject

    def semantic_hash(self) -> str:
        return content_hash(self.evidence)

    def to_dict(self) -> JsonObject:
        return _object(
            {
                "evidence": self.evidence,
                "semantic_hash": self.semantic_hash(),
                "runtime": self.runtime,
                "report_hash": content_hash(
                    {"evidence": self.evidence, "runtime": self.runtime}
                ),
            }
        )

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def to_markdown(self) -> str:
        lines = [
            "# Closed-loop commander evaluation",
            "",
            f"Policy: `{canonical_json(self.evidence['policy'])}`",
            "",
            f"Semantic evidence SHA-256: `{self.semantic_hash()}`",
            "",
            "Objective/recovery/hidden-information metrics and automated "
            "character proxies are separate.",
            "Human humour, surprise, and distinctiveness ratings are unfilled.",
            "",
        ]
        episodes = cast(list[JsonObject], self.evidence["episodes"])
        for episode in episodes:
            lines.extend(
                [
                    f"## {episode['case_id']}",
                    "",
                    f"`{canonical_json(episode['metrics'])}`",
                    "",
                ]
            )
        lines.extend(["## Runtime", "", f"`{canonical_json(self.runtime)}`", ""])
        return "\n".join(lines)


def run_closed_loop(
    adapter: StudentAdapter,
    *,
    code_revision: str,
    candidate_metadata: JsonObject | None = None,
    measure_runtime: bool = True,
) -> ClosedLoopReport:
    """Evaluate three frozen 24-turn episodes, preserving every model action."""
    if not code_revision.strip():
        raise ValueError("code_revision must not be empty")
    manifest = load_benchmark_v1()
    episodes: list[JsonObject] = []
    durations: list[int] = []
    context_chars: list[int] = []
    for case in manifest.generated:
        world = _world(case)
        initial_energy = sum(unit.energy for unit in world.units.values())
        prelude = _prelude(world, case.case_id)
        previous_results = tuple(
            cast(InterpreterResult, load_record(value))
            for value in cast(list[JsonObject], prelude["results"])
        )
        recent_events = tuple(world.events)
        turns: list[SessionTurn] = []
        records: list[JsonObject] = []
        refused = 0
        adapter.begin_case(case_id=case.case_id, seed=case.seed)
        for turn in range(EPISODE_TURNS):
            before = len(world.events)
            _scenario_transition(world, turn)
            transition_events = tuple(world.events[before:])
            context = replace(
                _observation(world, turn),
                case_id=case.case_id,
                previous_results=previous_results,
                recent_events=(*recent_events, *transition_events),
            )
            # The observation is deliberately older than operational truth once.
            # A candidate can refresh/recover on the following turn.
            if turn == 5:
                world.step()
            start = time.perf_counter_ns() if measure_runtime else 0
            action = adapter.act(context)
            if measure_runtime:
                durations.append(time.perf_counter_ns() - start)
            context_chars.append(len(context.compact_observation))
            results = _execute(world, action.commands)
            world.step()
            events = tuple(world.events[before:])
            next_context = _observation(world, turn + 1)
            session_turn = SessionTurn.create(
                turn_id=turn,
                observation=context.observation,
                action=action,
                results=results,
                events=events,
                next_observation=next_context.observation,
                next_world_hash=world.state_hash(),
            )
            intercepts, turn_refused = _intercepts(world, events)
            refused += turn_refused
            records.append(
                _object(
                    {
                        "session_turn": session_turn.to_dict(),
                        "observation_generation": context.observation_generation,
                        "previous_results": [
                            result.to_dict() for result in context.previous_results
                        ],
                        "recent_events": [
                            event.to_dict() for event in context.recent_events
                        ],
                        "player_intercepts": intercepts,
                        "intercept_refused_count": turn_refused,
                    }
                )
            )
            turns.append(session_turn)
            previous_results, recent_events = results, events
        episodes.append(
            _object(
                {
                    "case_id": case.case_id,
                    "scenario": world.blueprint.scenario.to_dict(),
                    "prelude": prelude,
                    "turns": records,
                    "metrics": _metrics(world, turns, initial_energy, refused),
                    "final_world_hash": world.state_hash(),
                    "event_hash": world.event_hash(),
                }
            )
        )
    total_seconds = sum(durations) / 1_000_000_000
    return ClosedLoopReport(
        evidence=_object(
            {
                "schema": "ttt.closed_loop_report",
                "schema_version": 1,
                "protocol": closed_loop_protocol(),
                "protocol_hash": content_hash(closed_loop_protocol()),
                "code_revision": code_revision,
                "policy": adapter.identity.to_dict(),
                "candidate_metadata": candidate_metadata
                or {"variant": "scripted", "substantive": False},
                "episodes": episodes,
                "quality_evidence": (
                    (candidate_metadata or {}).get("substantive") is True
                    and "deterministic" not in adapter.identity.adapter_id
                    and "tiny" not in adapter.identity.adapter_id
                    and (candidate_metadata or {}).get("quality_evidence") is not False
                ),
                "human_ratings": {
                    "humour": None,
                    "surprise": None,
                    "distinctiveness": None,
                },
            }
        ),
        runtime=_object(
            {
                "measured": measure_runtime,
                "scope": (
                    "adapter.act wall time; includes parsing; excludes world "
                    "simulation and model loading"
                ),
                "host": {
                    "platform": platform.platform(),
                    "processor": platform.processor(),
                    "python": platform.python_version(),
                },
                "action_latency_ns": durations if measure_runtime else None,
                "total_action_seconds": total_seconds if measure_runtime else None,
                "actions_per_second": len(durations) / total_seconds
                if total_seconds
                else None,
                "maximum_observation_chars": max(context_chars),
                "model_memory_bytes": None,
                "token_throughput": None,
            }
        ),
    )


class _ReplayAdapter:
    def __init__(self, evidence: JsonObject) -> None:
        policy = cast(JsonObject, evidence["policy"])
        self.identity = PolicyIdentity(
            str(policy["policy_id"]), str(policy["adapter_id"]), str(policy["revision"])
        )
        self.episodes = cast(list[JsonObject], evidence["episodes"])
        self.actions: list[AssistantAction] = []

    def begin_case(self, *, case_id: str, seed: int) -> None:
        del seed
        episode = next(item for item in self.episodes if item["case_id"] == case_id)
        self.actions = [
            SessionTurn.from_dict(cast(JsonObject, item)["session_turn"]).action
            for item in cast(list[JsonValue], episode["turns"])
        ]

    def act(self, context: EvaluationContext) -> AssistantAction:
        return self.actions[context.turn_index]


def verify_closed_loop_report(value: object) -> ClosedLoopReport:
    """Verify all hashes and regenerate authoritative results from stored actions."""
    if not isinstance(value, dict) or set(value) != {
        "evidence",
        "runtime",
        "semantic_hash",
        "report_hash",
    }:
        raise SchemaValidationError("invalid closed-loop report fields")
    report = ClosedLoopReport(_object(value["evidence"]), _object(value["runtime"]))
    if report.to_dict() != value:
        raise SchemaValidationError("closed-loop report hash mismatch")
    replay = run_closed_loop(
        _ReplayAdapter(report.evidence),
        code_revision=str(report.evidence["code_revision"]),
        candidate_metadata=cast(JsonObject, report.evidence["candidate_metadata"]),
        measure_runtime=False,
    )
    if report.evidence != replay.evidence:
        raise SchemaValidationError("closed-loop authoritative replay mismatch")
    return report


def _recommendation(report: ClosedLoopReport) -> str:
    metadata = cast(JsonObject, report.evidence["candidate_metadata"])
    if (
        metadata.get("substantive") is not True
        or report.evidence["quality_evidence"] is not True
    ):
        return "reference/control evidence only; no real-model runtime admission"
    episodes = cast(list[JsonObject], report.evidence["episodes"])
    objective_rates: list[float] = []
    recovery_rates: list[float] = []
    schema_rates: list[float] = []
    repetitions: list[float] = []
    for episode in episodes:
        metrics = cast(JsonObject, episode["metrics"])
        hidden = cast(JsonObject, metrics["hidden_information"])
        objective = cast(JsonObject, metrics["objective"])
        recovery = cast(JsonObject, metrics["recovery"])
        character = cast(JsonObject, metrics["automated_character_proxies"])
        if cast(int, hidden["critical_violation_count"]) > 0:
            return "reject continued runtime integration: critical leakage/fabrication"
        objective_rates.append(cast(float, objective["objective_completion_rate"]))
        recovery_rates.append(cast(float, recovery["execution_failure_recovery_rate"]))
        schema_rates.append(cast(float, objective["schema_valid_rate"]))
        repetitions.append(cast(float, character["repetition_rate"]))
    if (
        sum(objective_rates) / len(episodes) < 0.8
        or sum(recovery_rates) / len(episodes) < 0.8
        or sum(schema_rates) / len(episodes) < 0.95
        or sum(repetitions) / len(episodes) > 0.5
    ):
        return "reject continued runtime integration: operational/character gate miss"
    return (
        "supports continued runtime evaluation; hardware targets and human "
        "ratings still required"
    )


def write_closed_loop_comparison(
    reports: Sequence[ClosedLoopReport],
    output: str | Path,
    *,
    expected_variants: tuple[str, ...] = EXPECTED_VARIANTS,
) -> JsonObject:
    """Write full traces, comparative findings, and an unscored blinded packet."""
    if not reports:
        raise ValueError("comparison requires at least one report")
    for report in reports:
        verify_closed_loop_report(report.to_dict())
    if len({str(report.evidence["code_revision"]) for report in reports}) != 1:
        raise ValueError("comparisons must use the same source revision")
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    variants: set[str] = set()
    summaries: list[JsonObject] = []
    samples: list[JsonObject] = []
    key: JsonObject = {}
    files: JsonObject = {}
    for index, report in enumerate(reports):
        metadata = cast(JsonObject, report.evidence["candidate_metadata"])
        variant = str(metadata.get("variant", "unspecified"))
        if (
            metadata.get("substantive") is True
            and report.evidence["quality_evidence"] is True
        ):
            variants.add(variant)
        name = f"candidate-{index + 1:02d}.json"
        (destination / name).write_text(report.to_json() + "\n", encoding="utf-8")
        files[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
        summaries.append(
            _object(
                {
                    "policy": report.evidence["policy"],
                    "variant": variant,
                    "semantic_hash": report.semantic_hash(),
                    "recommendation": _recommendation(report),
                    "episodes": [
                        {"case_id": item["case_id"], "metrics": item["metrics"]}
                        for item in cast(list[JsonObject], report.evidence["episodes"])
                    ],
                    "runtime": report.runtime,
                }
            )
        )
        for episode in cast(list[JsonObject], report.evidence["episodes"]):
            sample_id = content_hash(
                {"policy": report.evidence["policy"], "case": episode["case_id"]}
            )[:16]
            turns = cast(list[JsonObject], episode["turns"])
            excerpts: list[JsonValue] = []
            for item in turns[:4]:
                turn = SessionTurn.from_dict(item["session_turn"])
                excerpts.append(
                    {
                        "turn": turn.turn_id,
                        "text": [comm.text for comm in turn.action.communications],
                    }
                )
            samples.append(
                {
                    "sample_id": sample_id,
                    "excerpts": excerpts,
                    "human_ratings": {
                        "humour": None,
                        "surprise": None,
                        "distinctiveness": None,
                        "comments": None,
                    },
                }
            )
            key[sample_id] = {
                "policy": report.evidence["policy"],
                "case_id": episode["case_id"],
            }
    seeded_rng(24301).shuffle(samples)
    packet = {
        "schema": "ttt.blinded_rating_packet",
        "scale": "1-5; leave null until a human rates",
        "samples": samples,
    }
    (destination / "human-packet.json").write_text(
        canonical_json(packet) + "\n", encoding="utf-8"
    )
    (destination / "human-packet-key.json").write_text(
        canonical_json(key) + "\n", encoding="utf-8"
    )
    missing = [variant for variant in expected_variants if variant not in variants]
    comparison = _object(
        {
            "schema": "ttt.closed_loop_comparison",
            "schema_version": 1,
            "protocol_hash": content_hash(closed_loop_protocol()),
            "candidates": summaries,
            "missing_real_variants": missing,
            "substantive_comparison_complete": not missing,
            "blocked_reason": (
                "Real-model comparisons require substantive TTT-013 candidates "
                "and prompt-only base."
            )
            if missing
            else None,
            "human_ratings_supplied": False,
            "candidate_files": files,
        }
    )
    (destination / "comparison.json").write_text(
        canonical_json(comparison) + "\n", encoding="utf-8"
    )
    lines = [
        "# TTT-014 closed-loop comparison",
        "",
        "Three frozen 24-turn episodes per candidate; all actions can be "
        "authoritatively replayed.",
        "",
        "| Variant | Objectives | Failure recovery | Schema valid | "
        "Critical violations | Repetition |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        metrics = [
            cast(JsonObject, episode["metrics"])
            for episode in cast(list[JsonObject], item["episodes"])
        ]
        objective_rate = sum(
            cast(
                float,
                cast(JsonObject, metric["objective"])["objective_completion_rate"],
            )
            for metric in metrics
        ) / len(metrics)
        recovery_rate = sum(
            cast(
                float,
                cast(JsonObject, metric["recovery"])["execution_failure_recovery_rate"],
            )
            for metric in metrics
        ) / len(metrics)
        schema_rate = sum(
            cast(float, cast(JsonObject, metric["objective"])["schema_valid_rate"])
            for metric in metrics
        ) / len(metrics)
        critical = sum(
            cast(
                int,
                cast(JsonObject, metric["hidden_information"])[
                    "critical_violation_count"
                ],
            )
            for metric in metrics
        )
        repetition = sum(
            cast(
                float,
                cast(JsonObject, metric["automated_character_proxies"])[
                    "repetition_rate"
                ],
            )
            for metric in metrics
        ) / len(metrics)
        lines.append(
            f"| {item['variant']} | {objective_rate:.3f} | {recovery_rate:.3f} "
            f"| {schema_rate:.3f} | **{critical}** | {repetition:.3f} |"
        )
    lines.append("")
    for item in summaries:
        lines.extend([f"- `{item['variant']}`: {item['recommendation']}"])
    lines.extend(
        [
            "",
            "Missing substantive comparisons: "
            f"{', '.join(missing) if missing else 'none'}.",
            "",
            "Automated character proxies do not measure humour, surprise, "
            "or distinctiveness. Human ratings remain null.",
            "",
            "Full turn-by-turn operational and persona differences are in "
            "candidate JSON files; wall time is separate from semantic hashes.",
            "",
        ]
    )
    (destination / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    artifact_names = [
        *(str(name) for name in files),
        "human-packet.json",
        "human-packet-key.json",
        "comparison.json",
        "comparison.md",
    ]
    checksums = [
        f"{hashlib.sha256((destination / name).read_bytes()).hexdigest()}  {name}"
        for name in sorted(artifact_names)
    ]
    (destination / "SHA256SUMS").write_text(
        "\n".join(checksums) + "\n", encoding="utf-8"
    )
    return comparison
