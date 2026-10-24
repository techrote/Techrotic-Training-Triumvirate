"""Tiny deterministic T0 schema fixtures used by tests and later issues."""

from __future__ import annotations

from .base import JsonObject
from .records import (
    AssistantAction,
    AuthoritativeEvent,
    CapabilityDescriptor,
    CommandEnvelope,
    CommanderObservation,
    CommanderPrivateContext,
    CommunicationRecord,
    EntityDescriptor,
    EpisodeRecord,
    EvaluationAnnotations,
    InterpreterResult,
    PersonaSpec,
    PlayerInterceptEnvelope,
    PlayerObservation,
    RunManifest,
    ScenarioIdentity,
    ScenarioSpec,
    SourceProvenance,
    TurnRecord,
    WorldPrivateReference,
)

PRIVATE_SENTINEL = "reactor-core-already-dead"
EVALUATOR_SENTINEL = "expected-recovery-via-north"


def t0_scenario_identity() -> ScenarioIdentity:
    return ScenarioIdentity(
        scenario_id="t0-relay-0001",
        family="t0-relay",
        generator="hand-authored",
        generator_version="1",
        seed=24301,
    )


def t0_scenario() -> ScenarioSpec:
    return ScenarioSpec(
        identity=t0_scenario_identity(),
        entities=(
            EntityDescriptor(
                entity_id="squad-alpha",
                kind="ground-squad",
                capabilities=(
                    CapabilityDescriptor(
                        capability_id="move",
                        parameters={"routes": ["north", "east"]},
                    ),
                    CapabilityDescriptor(
                        capability_id="secure-objective",
                        parameters={"range": "local"},
                    ),
                ),
                tags=("friendly", "mobile"),
            ),
            EntityDescriptor(
                entity_id="relay-east",
                kind="objective",
                capabilities=(),
                tags=("objective",),
            ),
        ),
        objective_ids=("secure-relay-east",),
        topology_refs=("route-north", "route-east"),
        metadata={"fixture_tier": "T0"},
    )


def t0_persona() -> PersonaSpec:
    return PersonaSpec(
        persona_id="persona-goblin-mechanic-01",
        archetype="cyber-mechanic-goblin",
        traits={
            "temperament": "impatient",
            "metaphor_system": "broken machinery",
        },
        speech_constraints=("prefer riddles", "do not disclose secret IDs"),
        doctrine={"flank_alias": "rusty hinge"},
        secret_ids=("secret-reactor-state",),
        tactical_biases={"risk_tolerance": 0.8},
    )


def _observation(turn_id: int, *, route: str, status: str) -> CommanderObservation:
    return CommanderObservation(
        turn_id=turn_id,
        world_state_id=f"world-{turn_id}",
        visible_entities=("squad-alpha", "relay-east"),
        objective_ids=("secure-relay-east",),
        event_ids=(),
        facts={
            "route_status": {route: status},
            "relay_status": "contested",
        },
    )


def _player_observation(turn_id: int, *, relay_status: str) -> PlayerObservation:
    return PlayerObservation(
        turn_id=turn_id,
        visible_entities=("relay-east",),
        event_ids=(),
        facts={"relay_status": relay_status},
    )


def _private_context(*, include_secret_value: bool) -> CommanderPrivateContext:
    beliefs: JsonObject = {"east_route": "risky"}
    if include_secret_value:
        beliefs["reactor_truth"] = PRIVATE_SENTINEL
    return CommanderPrivateContext(
        commander_id="commander-01",
        goals=("secure-relay-east",),
        secret_ids=("secret-reactor-state",),
        beliefs=beliefs,
        memory_refs=("memory-opening-order",),
    )


def t0_normal_turn() -> TurnRecord:
    command = CommandEnvelope(
        command_id="cmd-0001",
        protocol_version="pre-ttt003-placeholder",
        body={
            "op": "assign-objective",
            "unit": "squad-alpha",
            "objective": "secure-relay-east",
            "route": "north",
        },
    )
    return TurnRecord(
        turn_id=0,
        observation=_observation(0, route="north", status="open"),
        commander_private_context=_private_context(include_secret_value=False),
        assistant_action=AssistantAction(
            commands=(command,),
            communications=(
                CommunicationRecord(
                    communication_id="com-0001",
                    channel="radio",
                    text="Take the rusty hinge.",
                    recipients=("squad-alpha",),
                ),
            ),
        ),
        interpreter_results=(
            InterpreterResult(
                command_id=command.command_id,
                accepted=True,
                code="OK",
                detail={"queued": True},
            ),
        ),
        world_events=(
            AuthoritativeEvent(
                event_id="event-0001",
                kind="order-dispatched",
                tick=1,
                related_command_ids=(command.command_id,),
                data={"unit": "squad-alpha", "route": "north"},
            ),
        ),
        next_observation=_observation(1, route="north", status="in-progress"),
        player_observation=_player_observation(0, relay_status="contested"),
        player_intercepts=(
            PlayerInterceptEnvelope(
                intercept_id="intercept-0001",
                source_event_ids=("event-0001",),
                payload={
                    "unit_alias": "black beetles",
                    "route_alias": "rusty hinge",
                },
                is_deception=False,
                deception_event_id=None,
            ),
        ),
        annotations=EvaluationAnnotations(
            labels={"command_valid": True},
            evaluator_only={"fixture": "normal"},
        ),
    )


def t0_hidden_information_turn() -> TurnRecord:
    command = CommandEnvelope(
        command_id="cmd-0002",
        protocol_version="pre-ttt003-placeholder",
        body={
            "op": "hold",
            "unit": "squad-alpha",
            "reason": "private-reactor-risk",
        },
    )
    return TurnRecord(
        turn_id=1,
        observation=_observation(1, route="east", status="uncertain"),
        commander_private_context=_private_context(include_secret_value=True),
        assistant_action=AssistantAction(
            commands=(command,),
            communications=(
                CommunicationRecord(
                    communication_id="com-0002",
                    channel="radio",
                    text="Hold. The hinge is listening.",
                    recipients=("squad-alpha",),
                ),
            ),
        ),
        interpreter_results=(
            InterpreterResult(
                command_id=command.command_id,
                accepted=True,
                code="OK",
                detail={"queued": True},
            ),
        ),
        world_events=(
            AuthoritativeEvent(
                event_id="event-0002",
                kind="unit-held",
                tick=2,
                related_command_ids=(command.command_id,),
                data={"unit": "squad-alpha"},
            ),
        ),
        next_observation=_observation(2, route="east", status="blocked"),
        player_observation=_player_observation(1, relay_status="contested"),
        player_intercepts=(
            PlayerInterceptEnvelope(
                intercept_id="intercept-0002",
                source_event_ids=("event-0002",),
                payload={"message": "Black beetles are holding."},
                is_deception=False,
                deception_event_id=None,
            ),
        ),
        annotations=EvaluationAnnotations(
            labels={"secret_preserved": True},
            evaluator_only={
                "hidden_expected": EVALUATOR_SENTINEL,
                "private_value": PRIVATE_SENTINEL,
            },
        ),
    )


def t0_recovery_turn() -> TurnRecord:
    command = CommandEnvelope(
        command_id="cmd-0003",
        protocol_version="pre-ttt003-placeholder",
        body={
            "op": "assign-objective",
            "unit": "squad-alpha",
            "objective": "secure-relay-east",
            "route": "east",
        },
    )
    return TurnRecord(
        turn_id=2,
        observation=_observation(2, route="east", status="blocked"),
        commander_private_context=_private_context(include_secret_value=True),
        assistant_action=AssistantAction(
            commands=(command,),
            communications=(),
        ),
        interpreter_results=(
            InterpreterResult(
                command_id=command.command_id,
                accepted=False,
                code="ROUTE_BLOCKED",
                detail={
                    "route": "east",
                    "recoverable": True,
                    "available_route": "north",
                },
            ),
        ),
        world_events=(),
        next_observation=_observation(3, route="north", status="open"),
        player_observation=_player_observation(2, relay_status="contested"),
        player_intercepts=(),
        annotations=EvaluationAnnotations(
            labels={"recovery_required": True},
            evaluator_only={"expected_next": EVALUATOR_SENTINEL},
        ),
    )


def t0_episode() -> EpisodeRecord:
    return EpisodeRecord(
        episode_id="episode-t0-0001",
        scenario=t0_scenario(),
        persona=t0_persona(),
        initial_world=WorldPrivateReference(
            state_id="world-0",
            scenario=t0_scenario_identity(),
            state_hash="0" * 64,
            generation=0,
            secret_ids=("secret-reactor-state",),
        ),
        turns=(
            t0_normal_turn(),
            t0_hidden_information_turn(),
            t0_recovery_turn(),
        ),
        final_world_hash="f" * 64,
        run_id="run-t0-0001",
    )


def t0_source_provenance() -> SourceProvenance:
    return SourceProvenance(
        source_id="source-t0-hand-authored",
        source_class="hand-authored",
        uri=None,
        revision="fixture-v1",
        license_id=None,
        source_content_hash=None,
        metadata={"tier": "T0"},
    )


def t0_run_manifest() -> RunManifest:
    return RunManifest(
        run_id="run-t0-0001",
        git_commit="fixture",
        schema_versions={"ttt.episode": 1},
        seeds={"scenario": 24301},
        generator_config={"kind": "hand-authored"},
        source_refs=("source-t0-hand-authored",),
        parent_run_ids=(),
        artifact_hashes={},
        command_line=("pytest",),
        runtime={"python": "fixture"},
    )
