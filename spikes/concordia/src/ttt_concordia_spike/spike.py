"""End-to-end Concordia deterministic Game Master proof."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from concordia.environment.engines import sequential

from .concordia_adapter import (
    ExplodingLanguageModel,
    ScriptedEntity,
    build_game_master,
)
from .world import TttCommand, WorldAuthority


VALID_COMMAND_JSON = '{"op":"move","target":"relay","route":"flank"}'


def semantic_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_demo() -> dict[str, Any]:
    world = WorldAuthority()
    model = ExplodingLanguageModel()
    game_master, resolver = build_game_master(world, model)

    commander = ScriptedEntity("Commander", [VALID_COMMAND_JSON])
    player = ScriptedEntity("Player")
    engine = sequential.Sequential()
    concordia_log: list[dict[str, Any]] = []

    private_before = world.world_private()

    engine.run_loop(
        game_masters=[game_master],
        entities=[commander, player],
        max_steps=1,
        log=concordia_log,
    )

    commander_after = json.loads(engine.make_observation(game_master, commander))
    player_after = json.loads(engine.make_observation(game_master, player))
    private_after = world.world_private()

    if resolver.last_command is None:
        raise AssertionError("Concordia engine did not route the typed command to resolution.")

    return {
        "typed_command": resolver.last_command.to_dict(),
        "private_before": private_before,
        "private_after": private_after,
        "commander_after": commander_after,
        "player_after": player_after,
        "world_hash": world.semantic_hash(),
        "commander_surface_hash": semantic_hash(commander_after),
        "player_surface_hash": semantic_hash(player_after),
        "model_calls": model.calls,
        "engine_steps_logged": len(concordia_log),
        "resolution": world.last_resolution.to_dict() if world.last_resolution else None,
    }


def parse_command(text: str) -> TttCommand:
    return TttCommand.from_json(text)
