"""Tiny deterministic TTT-style world used only by the LangGraph spike."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal, TypedDict


class Command(TypedDict):
    op: Literal["move"]
    target: Literal["relay"]
    route: Literal["direct", "flank"]


class WorldState(TypedDict):
    location: Literal["staging", "relay"]
    relay_secured: bool
    blocked_routes: list[str]
    private_fact: str


class CommanderObservation(TypedDict):
    location: Literal["staging", "relay"]
    relay_secured: bool
    known_blocked_routes: list[str]


class CommandResult(TypedDict):
    accepted: bool
    code: str
    detail: str


class WorldEvent(TypedDict):
    kind: str
    route: str
    outcome: str


class SpikeState(TypedDict):
    world: WorldState
    observation: CommanderObservation
    command: Command
    result: CommandResult | None
    events: list[WorldEvent]


def blocked_direct_command() -> Command:
    return {"op": "move", "target": "relay", "route": "direct"}


def corrected_flank_command() -> Command:
    return {"op": "move", "target": "relay", "route": "flank"}


def initial_world() -> WorldState:
    return {
        "location": "staging",
        "relay_secured": False,
        "blocked_routes": ["direct"],
        "private_fact": "relay-backup-generator-online",
    }


def commander_observation(world: WorldState) -> CommanderObservation:
    """Expose only the commander-visible projection of authoritative state."""
    return {
        "location": world["location"],
        "relay_secured": world["relay_secured"],
        "known_blocked_routes": list(world["blocked_routes"]),
    }


def initial_state(command: Command | None = None) -> SpikeState:
    world = initial_world()
    return {
        "world": world,
        "observation": commander_observation(world),
        "command": command or blocked_direct_command(),
        "result": None,
        "events": [],
    }


def apply_command(
    world: WorldState, command: Command
) -> tuple[WorldState, CommandResult, list[WorldEvent]]:
    """Apply one high-level command without any model or external side effect."""
    next_world = deepcopy(world)

    if command["op"] != "move" or command["target"] != "relay":
        return (
            next_world,
            {
                "accepted": False,
                "code": "COMMAND_INVALID",
                "detail": "Only move-to-relay is supported by the spike world.",
            },
            [
                {
                    "kind": "command_rejected",
                    "route": command["route"],
                    "outcome": "COMMAND_INVALID",
                }
            ],
        )

    if command["route"] in world["blocked_routes"]:
        return (
            next_world,
            {
                "accepted": False,
                "code": "ROUTE_BLOCKED",
                "detail": f"Route {command['route']} is blocked.",
            },
            [
                {
                    "kind": "command_rejected",
                    "route": command["route"],
                    "outcome": "ROUTE_BLOCKED",
                }
            ],
        )

    next_world["location"] = "relay"
    next_world["relay_secured"] = True
    return (
        next_world,
        {
            "accepted": True,
            "code": "OK",
            "detail": f"Relay reached via {command['route']}.",
        },
        [
            {
                "kind": "command_executed",
                "route": command["route"],
                "outcome": "RELAY_SECURED",
            }
        ],
    )
