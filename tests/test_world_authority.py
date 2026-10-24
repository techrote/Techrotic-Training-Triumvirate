from __future__ import annotations

import json

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    CommandInterpreter,
    ErrorCode,
)
from techrotic_training_triumvirate.schemas import content_hash
from techrotic_training_triumvirate.world import (
    ObjectiveStatus,
    ScenarioConfig,
    ScenarioGenerator,
    UnitStatus,
    WorldAuthority,
    execute_envelope,
    run_envelopes,
    run_scripted_episode,
)


def blueprint(*, seed: int = 24301, mid_state: bool = False):
    return ScenarioGenerator().generate(
        seed=seed,
        config=ScenarioConfig(complexity=3, mid_state=mid_state),
    )


def assign(
    world: WorldAuthority,
    *,
    command_id: str,
    unit_id: str = "unit-1",
    route: str = "north",
    constraints: tuple[str, ...] = (),
) -> AssignObjectiveCommand:
    return AssignObjectiveCommand(
        command_id=command_id,
        observation_generation=world.observation_generation,
        unit_id=unit_id,
        objective_kind="secure",
        target_id="relay-east",
        approach=route,
        constraints=constraints,
    )


def test_seeded_scenario_generation_is_deterministic() -> None:
    first = blueprint(seed=11)
    second = blueprint(seed=11)
    other = blueprint(seed=12)

    assert first == second
    assert first.scenario.content_hash() == second.scenario.content_hash()
    assert first.scenario.identity.scenario_id != other.scenario.identity.scenario_id


def test_mid_state_generation_is_coherent_and_not_clean_start() -> None:
    clean = blueprint(seed=5, mid_state=False)
    mid = blueprint(seed=5, mid_state=True)

    assert clean.initial_tick == 0
    assert mid.initial_tick == 5
    assert mid.initial_generation == 5
    assert mid.units[0].status is UnitStatus.HOLDING
    assert mid.units[0].zone_id == "ridge"
    assert mid.units[0].energy < clean.units[0].energy


def test_blocked_route_is_delayed_execution_failure_after_admission() -> None:
    world = WorldAuthority(blueprint())
    command = assign(world, command_id="blocked", route="direct")

    result = execute_envelope(world, command.to_envelope())

    assert result.accepted is True
    assert [event.kind for event in world.events] == [
        "command-dispatched",
        "execution-failed",
    ]
    assert world.events[-1].data["code"] == "ROUTE_BLOCKED"
    assert world.units["unit-1"].current_order_id is None
    assert "direct" in world.discovered_routes


def test_stale_command_is_immediate_rejection_without_dispatch_mutation() -> None:
    world = WorldAuthority(blueprint())
    command = AssignObjectiveCommand(
        command_id="stale",
        observation_generation=99,
        unit_id="unit-1",
        objective_kind="secure",
        target_id="relay-east",
        approach="north",
        constraints=(),
    )

    outcome = CommandInterpreter().interpret(command.to_envelope(), world)

    assert outcome.result.accepted is False
    assert outcome.result.code == ErrorCode.STALE_OBSERVATION.value
    assert outcome.dispatch_event is None
    assert world.orders == {}
    assert world.events == []


def test_stall_and_resource_failures_happen_after_acceptance() -> None:
    stalled = WorldAuthority(blueprint())
    stalled_command = assign(
        stalled,
        command_id="stall",
        constraints=("simulate:stall",),
    )
    first = CommandInterpreter().interpret(stalled_command.to_envelope(), stalled)
    assert first.result.accepted is True
    assert first.dispatch_event is not None
    stalled.events.append(first.dispatch_event)
    assert stalled.step() == ()
    events = stalled.step()
    assert events[-1].data["code"] == "STALL_NO_PROGRESS"

    exhausted = WorldAuthority(blueprint())
    exhausted.units["unit-2"].energy = 1
    heavy_command = assign(
        exhausted,
        command_id="heavy-low-energy",
        unit_id="unit-2",
    )
    second = CommandInterpreter().interpret(heavy_command.to_envelope(), exhausted)
    assert second.result.accepted is True
    assert second.dispatch_event is not None
    exhausted.events.append(second.dispatch_event)
    events = exhausted.step()
    assert events[-1].data["code"] == "RESOURCE_EXHAUSTED"


def test_competing_orders_produce_target_state_change_failure() -> None:
    world = WorldAuthority(blueprint())
    first = assign(world, command_id="a-first", unit_id="unit-1")
    second = assign(world, command_id="b-second", unit_id="unit-2")

    for command in (first, second):
        outcome = CommandInterpreter().interpret(command.to_envelope(), world)
        assert outcome.result.accepted is True
        assert outcome.dispatch_event is not None
        world.events.append(outcome.dispatch_event)

    world.step()
    world.step()

    assert world.objectives["relay-east"].status is ObjectiveStatus.SECURED
    failure_codes = [
        event.data["code"] for event in world.events if event.kind == "execution-failed"
    ]
    assert "TARGET_STATE_CHANGED" in failure_codes


def test_private_commander_and_player_surfaces_are_distinct() -> None:
    world = WorldAuthority(blueprint())
    secret = world.blueprint.private_facts["enemy_reserve_zone"]
    private = world.private_snapshot()
    commander = world.commander_observation(turn_id=0)
    player = world.player_observation(turn_id=0)

    assert secret in json.dumps(private, sort_keys=True)
    assert str(secret) not in commander.to_json()
    assert str(secret) not in player.to_json()
    assert "energy" in commander.to_json()
    assert "energy" not in player.to_json()
    assert '"direct"' not in commander.to_json()

    execute_envelope(
        world,
        assign(world, command_id="discover-direct", route="direct").to_envelope(),
    )
    assert '"direct"' in world.commander_observation(turn_id=1).to_json()


def test_24_turn_reference_episode_is_replayable_from_recorded_envelopes() -> None:
    result = run_scripted_episode(seed=24301, turns=24)
    replay_blueprint = ScenarioGenerator().generate(
        seed=24301,
        config=ScenarioConfig(),
    )
    replay = run_envelopes(replay_blueprint, result.envelopes)

    assert len(result.envelopes) == 24
    assert result.final_state_hash == replay.final_state_hash
    assert result.event_hash == replay.event_hash
    assert result.commander_observation_hash == replay.commander_observation_hash
    assert result.player_observation_hash == replay.player_observation_hash
    assert any(event.kind == "execution-failed" for event in result.events)
    assert any(event.kind == "objective-completed" for event in result.events)


def test_repeated_reference_episode_has_identical_semantic_hashes() -> None:
    first = run_scripted_episode(seed=88, turns=24)
    second = run_scripted_episode(seed=88, turns=24)

    assert first.final_state_hash == second.final_state_hash
    assert first.event_hash == second.event_hash
    assert content_hash([event.to_dict() for event in first.events]) == content_hash(
        [event.to_dict() for event in second.events]
    )
