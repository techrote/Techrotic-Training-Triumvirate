from __future__ import annotations

import json

import pytest

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    CommandInterpreter,
    RequestStatusCommand,
)
from techrotic_training_triumvirate.schemas import SchemaValidationError
from techrotic_training_triumvirate.schemas.fixtures import (
    EVALUATOR_SENTINEL,
    PRIVATE_SENTINEL,
    t0_hidden_information_turn,
    t0_normal_turn,
)
from techrotic_training_triumvirate.session import (
    DeterministicRenderer,
    SessionRecording,
    apply_delta,
    compute_delta,
    execute_turn,
)
from techrotic_training_triumvirate.world import (
    ScenarioConfig,
    ScenarioGenerator,
    WorldAuthority,
)


def _world(*, seed: int = 24301, mid_state: bool = False) -> WorldAuthority:
    blueprint = ScenarioGenerator().generate(
        seed=seed,
        config=ScenarioConfig(mid_state=mid_state),
    )
    return WorldAuthority(blueprint)


def test_structured_compact_and_delta_rendering_are_deterministic() -> None:
    world = _world()
    renderer = DeterministicRenderer()
    observation = world.commander_observation(turn_id=0)
    command = AssignObjectiveCommand(
        command_id="render-direct",
        observation_generation=world.observation_generation,
        unit_id="unit-1",
        objective_kind="secure",
        target_id="relay-east",
        approach="direct",
        constraints=(),
    )
    before = len(world.events)
    outcome = CommandInterpreter().interpret(command.to_envelope(), world)
    assert outcome.dispatch_event is not None
    world.events.append(outcome.dispatch_event)
    world.step()
    assert len(world.events) > before
    next_observation = world.commander_observation(turn_id=1)

    delta = compute_delta(observation, next_observation)

    assert renderer.structured_observation(observation) == observation.to_payload()
    assert renderer.compact_delta(delta).startswith("DELTA ")
    assert apply_delta(observation, delta) == next_observation.to_payload()
    assert delta.base_hash == observation.content_hash()
    assert delta.target_hash == next_observation.content_hash()
    assert "" not in delta.set_values
    assert "/facts/units/unit-2/energy" not in delta.set_values


def test_compact_observation_has_stable_golden_rendering() -> None:
    observation = t0_normal_turn().observation

    assert DeterministicRenderer().compact_observation(observation) == (
        "TURN 0 | STATE world-0 | ENTITIES squad-alpha,relay-east | "
        "OBJECTIVES secure-relay-east | EVENTS - | "
        'FACTS {"relay_status":"contested","route_status":{"north":"open"}}'
    )


def test_rendering_excludes_evaluation_and_private_fixture_fields() -> None:
    turn = t0_hidden_information_turn()
    renderer = DeterministicRenderer()
    structured = json.dumps(
        renderer.structured_observation(turn.observation),
        sort_keys=True,
    )
    compact = renderer.compact_observation(turn.observation)

    assert EVALUATOR_SENTINEL not in structured
    assert EVALUATOR_SENTINEL not in compact
    assert PRIVATE_SENTINEL not in structured
    assert PRIVATE_SENTINEL not in compact


def test_console_result_text_is_exactly_derived_from_interpreter_result() -> None:
    world = _world()
    renderer = DeterministicRenderer()
    accepted = RequestStatusCommand(
        command_id="status-ok",
        observation_generation=world.observation_generation,
        entity_ids=("unit-1",),
    )
    accepted_result = CommandInterpreter().interpret(
        accepted.to_envelope(), world
    ).result
    assert renderer.compact_result(accepted_result).startswith("ACK status-ok OK ")

    stale = RequestStatusCommand(
        command_id="status-stale",
        observation_generation=99,
        entity_ids=("unit-1",),
    )
    stale_result = CommandInterpreter().interpret(stale.to_envelope(), world).result
    assert renderer.compact_result(stale_result) == (
        'ERR status-stale STALE_OBSERVATION '
        '{"command_generation":99,"world_generation":0}'
    )


def test_commander_renderer_excludes_private_world_fields() -> None:
    world = _world()
    renderer = DeterministicRenderer()
    private_value = str(world.blueprint.private_facts["enemy_reserve_zone"])
    observation = world.commander_observation(turn_id=0)

    structured = json.dumps(
        renderer.structured_observation(observation),
        sort_keys=True,
    )
    compact = renderer.compact_observation(observation)

    assert private_value not in structured
    assert private_value not in compact
    assert "private_facts" not in structured
    assert "private_facts" not in compact


def test_session_recording_persists_and_rejects_corrupted_hashes(tmp_path) -> None:
    recording = SessionRecording.new(
        session_id="session-persist",
        run_id="run-persist",
        seed=24301,
    )
    command = RequestStatusCommand(
        command_id="persist-status",
        observation_generation=0,
        entity_ids=("unit-1", "relay-east"),
    )
    recorded = execute_turn(recording, command.to_envelope())
    path = tmp_path / "session.json"
    recorded.write(path)

    loaded = SessionRecording.read(path)
    assert loaded == recorded
    assert loaded.semantic_hash() == recorded.semantic_hash()

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["turns"][0]["hashes"]["turn"] = "0" * 64
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SchemaValidationError, match="verification failed"):
        SessionRecording.read(path)


def test_mid_state_session_starts_from_coherent_nonzero_observation() -> None:
    recording = SessionRecording.new(
        session_id="session-mid",
        run_id="run-mid",
        seed=77,
        mid_state=True,
    )

    assert recording.initial_world.generation == 5
    assert recording.initial_observation.facts["tick"] == 5
    units = recording.initial_observation.facts["units"]
    assert isinstance(units, dict)
    assert units["unit-1"]["zone_id"] == "ridge"

    command = RequestStatusCommand(
        command_id="mid-status",
        observation_generation=5,
        entity_ids=("unit-1",),
    )
    advanced = execute_turn(recording, command.to_envelope())
    assert advanced.turns[0].observation == recording.initial_observation
    assert advanced.turns[0].next_observation.turn_id == 1
