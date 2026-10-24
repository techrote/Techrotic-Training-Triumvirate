from __future__ import annotations

import json

import pytest
from concordia.typing import entity as entity_lib

from ttt_concordia_spike.concordia_adapter import DeterministicResolution
from ttt_concordia_spike.spike import run_demo
from ttt_concordia_spike.world import TttCommand, WorldAuthority


def test_concordia_runs_typed_command_without_llm_and_mutates_world() -> None:
    evidence = run_demo()

    assert evidence["model_calls"] == 0
    assert evidence["engine_steps_logged"] == 1
    assert evidence["typed_command"] == {
        "op": "move",
        "target": "relay",
        "route": "flank",
    }
    assert evidence["resolution"]["accepted"] is True
    assert evidence["resolution"]["code"] == "OK"
    assert evidence["private_after"]["location"] == "relay"
    assert evidence["private_after"]["relay_secured"] is True


def test_visibility_surfaces_are_distinct_and_secret_safe() -> None:
    evidence = run_demo()
    private = evidence["private_after"]
    commander = evidence["commander_after"]
    player = evidence["player_after"]

    assert private["private_fact"] == "relay-backup-generator-online"
    assert private["commander_objective"] == "secure-relay"
    assert private["blocked_routes"] == ["direct"]

    assert commander["surface"] == "commander"
    assert commander["state"]["known_blocked_routes"] == ["direct"]
    assert commander["state"]["objective"] == "secure-relay"
    assert "private_fact" not in commander["state"]

    assert player["surface"] == "player"
    assert player["state"] == {
        "public_status": "relay-secured",
        "relay_secured": True,
    }
    assert "known_blocked_routes" not in player["state"]
    assert "objective" not in player["state"]
    assert "private_fact" not in player["state"]

    secret = private["private_fact"]
    assert secret not in json.dumps(commander)
    assert secret not in json.dumps(player)


def test_invalid_typed_command_rejected_before_world_mutation() -> None:
    world = WorldAuthority()
    resolver = DeterministicResolution(world)
    before = world.semantic_hash()

    resolver.pre_observe(
        '[putative_event] Commander: {"op":"move","target":"relay","route":"warp"}'
    )
    with pytest.raises(ValueError):
        resolver.pre_act(
            entity_lib.ActionSpec(
                call_to_action="resolve",
                output_type=entity_lib.OutputType.RESOLVE,
            )
        )

    assert world.semantic_hash() == before
    assert world.state.location == "staging"
    assert world.state.relay_secured is False


def test_blocked_but_well_typed_command_is_deterministically_rejected() -> None:
    world = WorldAuthority()
    command = TttCommand.from_json(
        '{"op":"move","target":"relay","route":"direct"}'
    )
    before = world.semantic_hash()

    result = world.resolve(command)

    assert result.accepted is False
    assert result.code == "ROUTE_BLOCKED"
    assert world.semantic_hash() == before


def test_repeated_runs_have_identical_semantic_outcomes() -> None:
    first = run_demo()
    second = run_demo()

    assert first["world_hash"] == second["world_hash"]
    assert first["commander_surface_hash"] == second["commander_surface_hash"]
    assert first["player_surface_hash"] == second["player_surface_hash"]
    assert first["typed_command"] == second["typed_command"]
