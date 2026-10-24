"""Seeded procedural scenario generation for the abstract World Authority."""

from __future__ import annotations

from dataclasses import dataclass

from techrotic_training_triumvirate.determinism import seeded_rng
from techrotic_training_triumvirate.schemas import (
    CapabilityDescriptor,
    EntityDescriptor,
    ScenarioIdentity,
    ScenarioSpec,
)

from .model import (
    ObjectiveSeed,
    ObjectiveStatus,
    RouteSpec,
    UnitArchetype,
    UnitSeed,
    UnitStatus,
    WorldBlueprint,
)


SCENARIO_GENERATOR_VERSION = "abstract-world-v1"


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    complexity: int = 2
    unit_count: int = 3
    mid_state: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.complexity <= 5:
            raise ValueError("complexity must be between 1 and 5")
        if not 1 <= self.unit_count <= 8:
            raise ValueError("unit_count must be between 1 and 8")


def default_archetypes() -> tuple[UnitArchetype, ...]:
    base_control = frozenset(
        {
            "command.assign_objective",
            "command.set_constraints",
            "command.coordinate",
            "command.order_control",
        }
    )
    return (
        UnitArchetype(
            archetype_id="scout",
            capabilities=base_control | {"mobility.fast", "sensor.route"},
            max_energy=8,
            move_cost=1,
            description="fast reconnaissance unit",
        ),
        UnitArchetype(
            archetype_id="heavy",
            capabilities=base_control | {"mobility.heavy", "breach"},
            max_energy=12,
            move_cost=2,
            description="slow durable objective unit",
        ),
        UnitArchetype(
            archetype_id="support",
            capabilities=base_control | {"support", "sensor.status"},
            max_energy=10,
            move_cost=1,
            description="coordination and support unit",
        ),
        UnitArchetype(
            archetype_id="skirmisher",
            capabilities=base_control | {"mobility.fast", "harass"},
            max_energy=9,
            move_cost=1,
            description="mobile pressure unit",
        ),
    )


class ScenarioGenerator:
    """Generate small coherent deterministic scenario blueprints."""

    def generate(
        self,
        *,
        seed: int,
        config: ScenarioConfig = ScenarioConfig(),
    ) -> WorldBlueprint:
        rng = seeded_rng(seed)
        archetypes = default_archetypes()
        objective_id = "relay-east"
        scenario_identity = ScenarioIdentity(
            scenario_id=f"abstract-{seed:016x}-{config.complexity}",
            family=f"abstract-c{config.complexity}",
            generator="ScenarioGenerator",
            generator_version=SCENARIO_GENERATOR_VERSION,
            seed=seed,
        )

        zones = (
            "staging",
            "relay-zone",
            "ridge",
            "lowland",
            "reserve",
        )
        routes = (
            RouteSpec(
                route_id="direct",
                origin_zone="staging",
                destination_zone="relay-zone",
                travel_ticks=1,
                blocked=True,
                commander_knows_blocked=False,
            ),
            RouteSpec(
                route_id="north",
                origin_zone="staging",
                destination_zone="relay-zone",
                travel_ticks=2,
                blocked=False,
                commander_knows_blocked=True,
            ),
            RouteSpec(
                route_id="south",
                origin_zone="staging",
                destination_zone="relay-zone",
                travel_ticks=3,
                blocked=False,
                hazard_period=4 if config.complexity >= 3 else None,
                commander_knows_blocked=True,
            ),
        )

        selected_archetypes = tuple(
            archetypes[index % len(archetypes)]
            for index in range(config.unit_count)
        )
        units: list[UnitSeed] = []
        for index, archetype in enumerate(selected_archetypes):
            status = UnitStatus.READY
            energy = archetype.max_energy
            zone = "staging"
            if config.mid_state and index == 0:
                status = UnitStatus.HOLDING
                energy = max(1, archetype.max_energy - 2)
                zone = "ridge"
            units.append(
                UnitSeed(
                    entity_id=f"unit-{index + 1}",
                    archetype_id=archetype.archetype_id,
                    zone_id=zone,
                    energy=energy,
                    status=status,
                )
            )

        objective_status = (
            ObjectiveStatus.CONTESTED
            if not config.mid_state
            else ObjectiveStatus.CONTESTED
        )
        objectives = (
            ObjectiveSeed(
                objective_id=objective_id,
                zone_id="relay-zone",
                status=objective_status,
            ),
        )

        entities = tuple(
            EntityDescriptor(
                entity_id=unit.entity_id,
                kind="unit",
                capabilities=tuple(
                    CapabilityDescriptor(
                        capability_id=capability,
                        parameters={},
                    )
                    for capability in sorted(
                        next(
                            item.capabilities
                            for item in archetypes
                            if item.archetype_id == unit.archetype_id
                        )
                    )
                ),
                tags=(unit.archetype_id,),
            )
            for unit in units
        ) + (
            EntityDescriptor(
                entity_id=objective_id,
                kind="objective",
                capabilities=(),
                tags=("objective", "relay"),
            ),
        )

        scenario = ScenarioSpec(
            identity=scenario_identity,
            entities=entities,
            objective_ids=(objective_id,),
            topology_refs=tuple(route.route_id for route in routes),
            metadata={
                "complexity": config.complexity,
                "mid_state": config.mid_state,
                "terrain_variant": rng.randrange(4),
            },
        )
        discovered = tuple(
            route.route_id for route in routes if route.commander_knows_blocked
        )
        return WorldBlueprint(
            scenario=scenario,
            seed=seed,
            zones=zones,
            routes=routes,
            units=tuple(units),
            objectives=objectives,
            archetypes=archetypes,
            private_facts={
                "relay_backup_state": (
                    "unstable" if rng.randrange(2) else "nominal"
                ),
                "enemy_reserve_zone": "reserve",
            },
            initial_tick=5 if config.mid_state else 0,
            initial_generation=5 if config.mid_state else 0,
            discovered_routes=discovered,
        )
