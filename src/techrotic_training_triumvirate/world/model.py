"""Framework-neutral deterministic abstract-world data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from techrotic_training_triumvirate.schemas import JsonObject, ScenarioSpec


class UnitStatus(str, Enum):
    READY = "ready"
    MOVING = "moving"
    HOLDING = "holding"
    LOST = "lost"


class ObjectiveStatus(str, Enum):
    CONTESTED = "contested"
    SECURED = "secured"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class UnitArchetype:
    archetype_id: str
    capabilities: frozenset[str]
    max_energy: int
    move_cost: int
    description: str


@dataclass(frozen=True, slots=True)
class RouteSpec:
    route_id: str
    origin_zone: str
    destination_zone: str
    travel_ticks: int
    blocked: bool = False
    hazard_period: int | None = None
    commander_knows_blocked: bool = False

    def __post_init__(self) -> None:
        if self.travel_ticks < 1:
            raise ValueError("route travel_ticks must be positive")
        if self.hazard_period is not None and self.hazard_period < 1:
            raise ValueError("route hazard_period must be positive")


@dataclass(frozen=True, slots=True)
class UnitSeed:
    entity_id: str
    archetype_id: str
    zone_id: str
    energy: int
    status: UnitStatus = UnitStatus.READY


@dataclass(frozen=True, slots=True)
class ObjectiveSeed:
    objective_id: str
    zone_id: str
    status: ObjectiveStatus = ObjectiveStatus.CONTESTED


@dataclass(frozen=True, slots=True)
class WorldBlueprint:
    scenario: ScenarioSpec
    seed: int
    zones: tuple[str, ...]
    routes: tuple[RouteSpec, ...]
    units: tuple[UnitSeed, ...]
    objectives: tuple[ObjectiveSeed, ...]
    archetypes: tuple[UnitArchetype, ...]
    private_facts: JsonObject
    initial_tick: int = 0
    initial_generation: int = 0
    discovered_routes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        route_ids = [route.route_id for route in self.routes]
        unit_ids = [unit.entity_id for unit in self.units]
        objective_ids = [objective.objective_id for objective in self.objectives]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("route IDs must be unique")
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("unit IDs must be unique")
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError("objective IDs must be unique")
        if self.initial_tick < 0 or self.initial_generation < 0:
            raise ValueError("initial tick/generation must be non-negative")


@dataclass(slots=True)
class UnitState:
    entity_id: str
    archetype_id: str
    zone_id: str
    energy: int
    status: UnitStatus
    current_order_id: str | None = None


@dataclass(slots=True)
class ObjectiveState:
    objective_id: str
    zone_id: str
    status: ObjectiveStatus


@dataclass(slots=True)
class PendingOrder:
    command_id: str
    op: str
    unit_ids: tuple[str, ...]
    target_id: str | None
    route_id: str | None
    accepted_tick: int
    remaining_ticks: int
    constraints: tuple[str, ...] = ()
    stalled_ticks: int = 0
    data: JsonObject = field(default_factory=dict)
