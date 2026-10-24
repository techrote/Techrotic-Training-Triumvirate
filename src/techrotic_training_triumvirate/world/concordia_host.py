"""Optional Concordia host for the framework-neutral World Authority.

Concordia is imported lazily so the base TTT runtime remains dependency-free.
Its string action/observation surface is transport only; TTT canonical envelopes,
typed commands, visibility projections, and semantic hashes remain authoritative.
"""

from __future__ import annotations

import importlib
from typing import Any, cast

from techrotic_training_triumvirate.commands import CommandInterpreter
from techrotic_training_triumvirate.schemas import (
    CommandEnvelope,
    content_hash,
    loads_record,
)

from .authority import WorldAuthority
from .driver import DirectRunResult
from .model import WorldBlueprint


class ConcordiaUnavailableError(RuntimeError):
    """Raised when the optional Concordia host is requested but not installed."""


def _module(name: str) -> Any:
    try:
        return cast(Any, importlib.import_module(name))
    except ModuleNotFoundError as exc:
        if exc.name == "concordia" or (exc.name and exc.name.startswith("concordia.")):
            raise ConcordiaUnavailableError(
                "install the 'concordia' optional dependency group"
            ) from exc
        raise


class _ScriptedEntity:
    def __init__(self, name: str, actions: tuple[str, ...] = ()) -> None:
        self.name = name
        self._actions = list(actions)
        self.observations: list[str] = []

    def act(self, action_spec: Any) -> str:
        if not self._actions:
            raise AssertionError(f"{self.name} was unexpectedly asked to act")
        action = self._actions.pop(0)
        validate = getattr(action_spec, "validate", None)
        if validate is not None:
            validate(action)
        return action

    def observe(self, observation: str) -> None:
        self.observations.append(observation)


class _DeterministicGameMaster:
    def __init__(
        self,
        world: WorldAuthority,
        *,
        entity_lib: Any,
        engine_lib: Any,
    ) -> None:
        self.name = "TTT World Authority"
        self._world = world
        self._entity_lib = entity_lib
        self._engine_lib = engine_lib
        self._putative_event = ""
        self.resolve_calls = 0

    def observe(self, observation: str) -> None:
        putative_tag = "[putative_event]"
        if observation.startswith(putative_tag):
            self._putative_event = observation[len(putative_tag) :].strip()

    def _observation(self, call_to_action: str) -> str:
        if "Commander" in call_to_action:
            return self._world.commander_observation(
                turn_id=self._world.generation
            ).to_json()
        if "Player" in call_to_action:
            return self._world.player_observation(
                turn_id=self._world.generation
            ).to_json()
        raise ValueError(f"unknown Concordia observation target: {call_to_action!r}")

    def _resolve(self) -> str:
        raw = self._putative_event
        if raw.startswith("Commander:"):
            raw = raw.split(":", 1)[1].strip()
        loaded = loads_record(raw, expected_type=CommandEnvelope)
        assert isinstance(loaded, CommandEnvelope)
        outcome = CommandInterpreter().interpret(loaded, self._world)
        if outcome.dispatch_event is not None:
            self._world.events.append(outcome.dispatch_event)
        self._world.step()
        self.resolve_calls += 1
        self._putative_event = ""
        return outcome.result.to_json()

    def act(self, action_spec: Any) -> str:
        output_type = action_spec.output_type
        output_value = getattr(output_type, "value", str(output_type))
        if output_value == "terminate":
            return "No"
        if output_value == "make_observation":
            return self._observation(action_spec.call_to_action)
        if output_value == "next_acting":
            return "Commander"
        if output_value == "next_action_spec":
            return self._engine_lib.action_spec_to_string(
                self._entity_lib.ActionSpec(
                    call_to_action="Return one canonical TTT command envelope.",
                    output_type=self._entity_lib.OutputType.FREE,
                    tag="ttt-command-envelope",
                )
            )
        if output_value == "resolve":
            return self._resolve()
        raise NotImplementedError(f"unsupported Concordia GM output: {output_value}")


def run_concordia_envelopes(
    blueprint: WorldBlueprint,
    envelopes: tuple[CommandEnvelope, ...],
) -> DirectRunResult:
    """Execute the same canonical command sequence through Concordia Sequential."""
    sequential = _module("concordia.environment.engines.sequential")
    engine_lib = _module("concordia.environment.engine")
    entity_lib = _module("concordia.typing.entity")

    world = WorldAuthority(blueprint)
    commander = _ScriptedEntity(
        "Commander",
        tuple(envelope.to_json() for envelope in envelopes),
    )
    player = _ScriptedEntity("Player")
    game_master = _DeterministicGameMaster(
        world,
        entity_lib=entity_lib,
        engine_lib=engine_lib,
    )
    engine = sequential.Sequential()
    engine.run_loop(
        game_masters=[game_master],
        entities=[commander, player],
        max_steps=len(envelopes),
        verbose=False,
        log=None,
    )
    if game_master.resolve_calls != len(envelopes):
        raise AssertionError(
            "Concordia did not resolve every supplied canonical command envelope"
        )
    turn_id = len(envelopes)
    return DirectRunResult(
        envelopes=envelopes,
        results=(),
        events=tuple(world.events),
        final_state_hash=world.state_hash(),
        event_hash=world.event_hash(),
        commander_observation_hash=content_hash(
            world.commander_observation(turn_id=turn_id)
        ),
        player_observation_hash=content_hash(world.player_observation(turn_id=turn_id)),
    )


def concordia_identity() -> str:
    """Return the installed optional Concordia distribution version."""
    metadata = _module("importlib.metadata")
    return str(metadata.version("gdm-concordia"))
