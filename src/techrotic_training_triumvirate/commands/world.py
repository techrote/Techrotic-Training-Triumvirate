"""Framework-neutral world adapter contract for command admission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from techrotic_training_triumvirate.schemas import JsonObject

from .model import TypedCommand


@dataclass(frozen=True, slots=True)
class EntitySnapshot:
    entity_id: str
    available: bool
    capabilities: frozenset[str]


@dataclass(frozen=True, slots=True)
class ValidationFailure:
    detail: JsonObject


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    event_id: str
    tick: int
    data: JsonObject


class WorldAdapter(Protocol):
    """Minimal deterministic surface required by CommandInterpreter."""

    @property
    def observation_generation(self) -> int: ...

    def entity(self, entity_id: str) -> EntitySnapshot | None: ...

    def target_exists(self, target_id: str) -> bool: ...

    def check_preconditions(
        self, command: TypedCommand
    ) -> ValidationFailure | None: ...

    def check_resources(self, command: TypedCommand) -> ValidationFailure | None: ...

    def check_order_conflict(
        self, command: TypedCommand
    ) -> ValidationFailure | None: ...

    def dispatch(self, command: TypedCommand) -> DispatchReceipt:
        """Commit one fully admitted command and return its authoritative event."""
        ...
