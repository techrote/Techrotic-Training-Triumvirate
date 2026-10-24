"""Tiny deterministic TTT world and strict typed command model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any


class Operation(str, Enum):
    MOVE = "move"


class Route(str, Enum):
    DIRECT = "direct"
    FLANK = "flank"


@dataclass(frozen=True)
class TttCommand:
    op: Operation
    target: str
    route: Route

    @classmethod
    def from_json(cls, text: str) -> "TttCommand":
        raw = json.loads(text)
        if not isinstance(raw, dict):
            raise ValueError("TTT command must be a JSON object.")
        expected = {"op", "target", "route"}
        if set(raw) != expected:
            raise ValueError(
                f"TTT command fields must be exactly {sorted(expected)}."
            )
        target = raw["target"]
        if target != "relay":
            raise ValueError("Only target='relay' is admitted by the spike.")
        try:
            op = Operation(raw["op"])
            route = Route(raw["route"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Unsupported TTT command enum value.") from exc
        return cls(op=op, target=target, route=route)

    def to_dict(self) -> dict[str, str]:
        return {
            "op": self.op.value,
            "target": self.target,
            "route": self.route.value,
        }


@dataclass
class WorldState:
    location: str = "staging"
    relay_secured: bool = False
    blocked_routes: tuple[str, ...] = ("direct",)
    private_fact: str = "relay-backup-generator-online"
    commander_objective: str = "secure-relay"
    public_status: str = "relay-contested"


@dataclass(frozen=True)
class Resolution:
    accepted: bool
    code: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorldAuthority:
    """Deterministic authority; Concordia never decides world truth."""

    def __init__(self) -> None:
        self.state = WorldState()
        self.last_resolution: Resolution | None = None

    def world_private(self) -> dict[str, Any]:
        data = asdict(self.state)
        data["blocked_routes"] = list(self.state.blocked_routes)
        return data

    def commander_view(self) -> dict[str, Any]:
        return {
            "location": self.state.location,
            "relay_secured": self.state.relay_secured,
            "known_blocked_routes": list(self.state.blocked_routes),
            "objective": self.state.commander_objective,
            "public_status": self.state.public_status,
        }

    def player_view(self) -> dict[str, Any]:
        return {
            "relay_secured": self.state.relay_secured,
            "public_status": self.state.public_status,
        }

    def resolve(self, command: TttCommand) -> Resolution:
        if command.op is not Operation.MOVE:
            resolution = Resolution(False, "COMMAND_INVALID", "Unsupported op.")
        elif command.route.value in self.state.blocked_routes:
            resolution = Resolution(
                False,
                "ROUTE_BLOCKED",
                f"Route {command.route.value} is blocked.",
            )
        else:
            self.state.location = "relay"
            self.state.relay_secured = True
            self.state.public_status = "relay-secured"
            resolution = Resolution(
                True,
                "OK",
                f"Relay secured via {command.route.value}.",
            )
        self.last_resolution = resolution
        return resolution

    def semantic_hash(self) -> str:
        payload = json.dumps(
            self.world_private(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
