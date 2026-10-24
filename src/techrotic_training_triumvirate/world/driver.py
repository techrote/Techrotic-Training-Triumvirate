"""Direct/native deterministic driver for World Authority episodes."""

from __future__ import annotations

from dataclasses import dataclass

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    CommandInterpreter,
    RequestStatusCommand,
    TypedCommand,
)
from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    CommandEnvelope,
    InterpreterResult,
    content_hash,
)

from .authority import WorldAuthority
from .model import WorldBlueprint
from .scenario import ScenarioConfig, ScenarioGenerator


@dataclass(frozen=True, slots=True)
class DirectRunResult:
    envelopes: tuple[CommandEnvelope, ...]
    results: tuple[InterpreterResult, ...]
    events: tuple[AuthoritativeEvent, ...]
    final_state_hash: str
    event_hash: str
    commander_observation_hash: str
    player_observation_hash: str


def execute_envelope(
    world: WorldAuthority,
    envelope: CommandEnvelope,
) -> InterpreterResult:
    """Interpret one command, record dispatch, then advance one world tick."""
    outcome = CommandInterpreter().interpret(envelope, world)
    if outcome.dispatch_event is not None:
        world.events.append(outcome.dispatch_event)
    world.step()
    return outcome.result


def run_envelopes(
    blueprint: WorldBlueprint,
    envelopes: tuple[CommandEnvelope, ...],
) -> DirectRunResult:
    """Replay an exact command-envelope sequence from a fresh blueprint."""
    world = WorldAuthority(blueprint)
    results = tuple(execute_envelope(world, envelope) for envelope in envelopes)
    turn_id = len(envelopes)
    return DirectRunResult(
        envelopes=envelopes,
        results=results,
        events=tuple(world.events),
        final_state_hash=world.state_hash(),
        event_hash=world.event_hash(),
        commander_observation_hash=content_hash(
            world.commander_observation(turn_id=turn_id)
        ),
        player_observation_hash=content_hash(
            world.player_observation(turn_id=turn_id)
        ),
    )


def _scripted_command(world: WorldAuthority, turn: int) -> TypedCommand:
    generation = world.observation_generation
    if turn == 0:
        return AssignObjectiveCommand(
            command_id="demo-000-direct",
            observation_generation=generation,
            unit_id="unit-1",
            objective_kind="secure",
            target_id="relay-east",
            approach="direct",
            constraints=(),
        )
    if turn == 1:
        return AssignObjectiveCommand(
            command_id="demo-001-flank",
            observation_generation=generation,
            unit_id="unit-1",
            objective_kind="secure",
            target_id="relay-east",
            approach="north",
            constraints=(),
        )
    if turn == 3:
        return AssignObjectiveCommand(
            command_id="demo-003-late-second-unit",
            observation_generation=generation,
            unit_id="unit-2",
            objective_kind="secure",
            target_id="relay-east",
            approach="north",
            constraints=(),
        )
    return RequestStatusCommand(
        command_id=f"demo-{turn:03d}-status",
        observation_generation=generation,
        entity_ids=("unit-1", "relay-east"),
    )


def run_scripted_episode(
    *,
    seed: int,
    turns: int = 24,
    mid_state: bool = False,
) -> DirectRunResult:
    """Run a deterministic model-free 20+ turn reference episode."""
    if turns < 1:
        raise ValueError("turns must be positive")
    blueprint = ScenarioGenerator().generate(
        seed=seed,
        config=ScenarioConfig(mid_state=mid_state),
    )
    world = WorldAuthority(blueprint)
    envelopes: list[CommandEnvelope] = []
    results: list[InterpreterResult] = []

    for turn in range(turns):
        command = _scripted_command(world, turn)
        envelope = command.to_envelope()
        envelopes.append(envelope)
        results.append(execute_envelope(world, envelope))

    return DirectRunResult(
        envelopes=tuple(envelopes),
        results=tuple(results),
        events=tuple(world.events),
        final_state_hash=world.state_hash(),
        event_hash=world.event_hash(),
        commander_observation_hash=content_hash(
            world.commander_observation(turn_id=turns)
        ),
        player_observation_hash=content_hash(
            world.player_observation(turn_id=turns)
        ),
    )
