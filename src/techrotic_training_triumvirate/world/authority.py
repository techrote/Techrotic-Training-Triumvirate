"""Deterministic framework-neutral World Authority."""

from __future__ import annotations

from dataclasses import asdict

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    CancelCommand,
    CoordinateCommand,
    DispatchReceipt,
    EntitySnapshot,
    HoldCommand,
    InspectCommand,
    RecallCommand,
    RequestStatusCommand,
    SetConstraintsCommand,
    TransmitCommand,
    TypedCommand,
    ValidationFailure,
)
from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    CommanderObservation,
    JsonObject,
    PlayerObservation,
    WorldPrivateReference,
    content_hash,
)

from .model import (
    ObjectiveState,
    ObjectiveStatus,
    PendingOrder,
    RouteSpec,
    UnitArchetype,
    UnitState,
    UnitStatus,
    WorldBlueprint,
)


class WorldAuthority:
    """Own abstract operational truth independently of orchestration frameworks."""

    def __init__(self, blueprint: WorldBlueprint) -> None:
        self.blueprint = blueprint
        self.tick = blueprint.initial_tick
        self.generation = blueprint.initial_generation
        self._archetypes = {item.archetype_id: item for item in blueprint.archetypes}
        self._routes = {item.route_id: item for item in blueprint.routes}
        self.units = {
            seed.entity_id: UnitState(
                entity_id=seed.entity_id,
                archetype_id=seed.archetype_id,
                zone_id=seed.zone_id,
                energy=seed.energy,
                status=seed.status,
            )
            for seed in blueprint.units
        }
        self.objectives = {
            seed.objective_id: ObjectiveState(
                objective_id=seed.objective_id,
                zone_id=seed.zone_id,
                status=seed.status,
            )
            for seed in blueprint.objectives
        }
        self.orders: dict[str, PendingOrder] = {}
        self.discovered_routes = set(blueprint.discovered_routes)
        self.events: list[AuthoritativeEvent] = []
        self._event_sequence = 0

    @property
    def observation_generation(self) -> int:
        return self.generation

    def _archetype(self, unit: UnitState) -> UnitArchetype:
        return self._archetypes[unit.archetype_id]

    def entity(self, entity_id: str) -> EntitySnapshot | None:
        unit = self.units.get(entity_id)
        if unit is not None:
            return EntitySnapshot(
                entity_id=entity_id,
                available=unit.status is not UnitStatus.LOST,
                capabilities=self._archetype(unit).capabilities,
            )
        objective = self.objectives.get(entity_id)
        if objective is not None:
            return EntitySnapshot(
                entity_id=entity_id,
                available=objective.status is not ObjectiveStatus.FAILED,
                capabilities=frozenset(),
            )
        return None

    def target_exists(self, target_id: str) -> bool:
        return target_id in self.objectives or target_id in self.blueprint.zones

    def check_preconditions(
        self,
        command: TypedCommand,
    ) -> ValidationFailure | None:
        if isinstance(command, AssignObjectiveCommand):
            objective = self.objectives[command.target_id]
            if objective.status is ObjectiveStatus.SECURED:
                return ValidationFailure(
                    {"reason": "target-already-secured", "target_id": command.target_id}
                )
            route_id = command.approach or "north"
            if route_id not in self._routes:
                return ValidationFailure(
                    {"reason": "route-unknown", "route_id": route_id}
                )
        elif isinstance(command, SetConstraintsCommand):
            unit = self.units[command.unit_id]
            if unit.current_order_id is None:
                return ValidationFailure(
                    {"reason": "no-active-order", "unit_id": command.unit_id}
                )
        elif isinstance(command, CoordinateCommand):
            if len(command.unit_ids) < 2:
                return ValidationFailure(
                    {"reason": "coordination-requires-multiple-units"}
                )
        elif isinstance(command, CancelCommand):
            unit = self.units[command.unit_id]
            if unit.current_order_id is None:
                return ValidationFailure(
                    {"reason": "no-active-order", "unit_id": command.unit_id}
                )
            if (
                command.order_id is not None
                and command.order_id != unit.current_order_id
            ):
                return ValidationFailure(
                    {
                        "reason": "order-id-mismatch",
                        "unit_id": command.unit_id,
                        "order_id": command.order_id,
                    }
                )
        return None

    def check_resources(
        self,
        command: TypedCommand,
    ) -> ValidationFailure | None:
        if isinstance(command, (AssignObjectiveCommand, RecallCommand)):
            unit = self.units[command.unit_id]
            if unit.energy <= 0:
                return ValidationFailure(
                    {
                        "resource": "energy",
                        "unit_id": command.unit_id,
                    }
                )
        return None

    def check_order_conflict(
        self,
        command: TypedCommand,
    ) -> ValidationFailure | None:
        if isinstance(command, (AssignObjectiveCommand, RecallCommand)):
            unit = self.units[command.unit_id]
            if unit.current_order_id is not None:
                return ValidationFailure(
                    {
                        "unit_id": command.unit_id,
                        "active_order_id": unit.current_order_id,
                    }
                )
        return None

    def _next_event_id(self, kind: str) -> str:
        self._event_sequence += 1
        return (
            f"{self.blueprint.scenario.identity.scenario_id}:"
            f"{self.tick}:{self._event_sequence}:{kind}"
        )

    def _receipt(
        self,
        *,
        command: TypedCommand,
        data: JsonObject,
    ) -> DispatchReceipt:
        return DispatchReceipt(
            event_id=self._next_event_id("dispatch"),
            tick=self.tick,
            data=data,
        )

    def dispatch(self, command: TypedCommand) -> DispatchReceipt:
        """Commit one fully admitted command to authoritative order state."""
        if isinstance(command, AssignObjectiveCommand):
            route_id = command.approach or "north"
            route = self._routes[route_id]
            unit = self.units[command.unit_id]
            unit.status = UnitStatus.MOVING
            unit.current_order_id = command.command_id
            self.orders[command.command_id] = PendingOrder(
                command_id=command.command_id,
                op=command.OP.value,
                unit_ids=(command.unit_id,),
                target_id=command.target_id,
                route_id=route_id,
                accepted_tick=self.tick,
                remaining_ticks=route.travel_ticks,
                constraints=command.constraints,
            )
            return self._receipt(
                command=command,
                data={
                    "unit_id": command.unit_id,
                    "target_id": command.target_id,
                    "approach": route_id,
                },
            )

        if isinstance(command, SetConstraintsCommand):
            unit = self.units[command.unit_id]
            if unit.current_order_id is None:
                raise RuntimeError("precondition drift: no order to constrain")
            order = self.orders[unit.current_order_id]
            order.data["constraints"] = command.constraints
            return self._receipt(
                command=command,
                data={"unit_id": command.unit_id},
            )

        if isinstance(command, HoldCommand):
            unit = self.units[command.unit_id]
            unit.status = UnitStatus.HOLDING
            return self._receipt(
                command=command,
                data={"unit_id": command.unit_id},
            )

        if isinstance(command, CancelCommand):
            unit = self.units[command.unit_id]
            active_order_id = unit.current_order_id
            if active_order_id is None:
                raise RuntimeError("precondition drift: no order to cancel")
            self.orders.pop(active_order_id, None)
            unit.current_order_id = None
            unit.status = UnitStatus.READY
            return self._receipt(
                command=command,
                data={
                    "unit_id": command.unit_id,
                    "cancelled_order_id": active_order_id,
                },
            )

        if isinstance(command, RecallCommand):
            unit = self.units[command.unit_id]
            destination = command.destination_id or "staging"
            unit.status = UnitStatus.MOVING
            unit.current_order_id = command.command_id
            self.orders[command.command_id] = PendingOrder(
                command_id=command.command_id,
                op=command.OP.value,
                unit_ids=(command.unit_id,),
                target_id=destination,
                route_id=None,
                accepted_tick=self.tick,
                remaining_ticks=2,
            )
            return self._receipt(
                command=command,
                data={
                    "unit_id": command.unit_id,
                    "target_id": destination,
                },
            )

        if isinstance(command, CoordinateCommand):
            return self._receipt(
                command=command,
                data={
                    "unit_ids": list(command.unit_ids),
                    "trigger": command.trigger,
                    "target_id": command.objective_id,
                },
            )

        if isinstance(command, TransmitCommand):
            return self._receipt(
                command=command,
                data={
                    "unit_ids": list(command.recipients),
                    "channel": command.channel,
                },
            )

        if isinstance(command, InspectCommand):
            return self._receipt(
                command=command,
                data={"unit_id": command.entity_id},
            )

        if isinstance(command, RequestStatusCommand):
            return self._receipt(
                command=command,
                data={"unit_ids": list(command.entity_ids)},
            )

        raise AssertionError(f"unhandled command type: {type(command).__name__}")

    def _event(
        self,
        *,
        kind: str,
        command_id: str,
        data: JsonObject,
    ) -> AuthoritativeEvent:
        event = AuthoritativeEvent(
            event_id=self._next_event_id(kind),
            kind=kind,
            tick=self.tick,
            related_command_ids=(command_id,),
            data=data,
        )
        self.events.append(event)
        return event

    def _finish_order(self, order: PendingOrder, unit: UnitState) -> None:
        self.orders.pop(order.command_id, None)
        unit.current_order_id = None
        if unit.status is not UnitStatus.LOST:
            unit.status = UnitStatus.READY

    def _fail_order(
        self,
        order: PendingOrder,
        unit: UnitState,
        *,
        code: str,
        data: JsonObject,
    ) -> AuthoritativeEvent:
        event_data: JsonObject = {
            "code": code,
            "unit_id": unit.entity_id,
            **data,
        }
        event = self._event(
            kind="execution-failed",
            command_id=order.command_id,
            data=event_data,
        )
        self._finish_order(order, unit)
        return event

    def step(self) -> tuple[AuthoritativeEvent, ...]:
        """Advance one deterministic physical/operational tick."""
        self.tick += 1
        self.generation += 1
        produced: list[AuthoritativeEvent] = []

        for command_id, order in sorted(tuple(self.orders.items())):
            unit = self.units[order.unit_ids[0]]
            if unit.status is UnitStatus.HOLDING:
                continue

            if order.target_id in self.objectives:
                objective = self.objectives[order.target_id]
                if objective.status is ObjectiveStatus.SECURED:
                    produced.append(
                        self._fail_order(
                            order,
                            unit,
                            code="TARGET_STATE_CHANGED",
                            data={"target_id": order.target_id},
                        )
                    )
                    continue

            if "simulate:stall" in order.constraints:
                order.stalled_ticks += 1
                if order.stalled_ticks >= 2:
                    produced.append(
                        self._fail_order(
                            order,
                            unit,
                            code="STALL_NO_PROGRESS",
                            data={"stalled_ticks": order.stalled_ticks},
                        )
                    )
                continue

            route: RouteSpec | None = None
            if order.route_id is not None:
                route = self._routes[order.route_id]
                if route.blocked:
                    self.discovered_routes.add(route.route_id)
                    produced.append(
                        self._fail_order(
                            order,
                            unit,
                            code="ROUTE_BLOCKED",
                            data={"route_id": route.route_id},
                        )
                    )
                    continue

            archetype = self._archetype(unit)
            if unit.energy < archetype.move_cost:
                produced.append(
                    self._fail_order(
                        order,
                        unit,
                        code="RESOURCE_EXHAUSTED",
                        data={"resource": "energy"},
                    )
                )
                continue

            if (
                route is not None
                and route.hazard_period is not None
                and (self.tick + self.blueprint.seed) % route.hazard_period == 0
            ):
                unit.status = UnitStatus.LOST
                produced.append(
                    self._fail_order(
                        order,
                        unit,
                        code="UNIT_LOST",
                        data={"route_id": route.route_id},
                    )
                )
                continue

            unit.energy -= archetype.move_cost
            order.remaining_ticks -= 1
            if order.remaining_ticks > 0:
                produced.append(
                    self._event(
                        kind="order-progress",
                        command_id=command_id,
                        data={
                            "unit_id": unit.entity_id,
                            "remaining_ticks": order.remaining_ticks,
                        },
                    )
                )
                continue

            if order.op == AssignObjectiveCommand.OP.value:
                if order.target_id is None:
                    raise RuntimeError("assign order lost target")
                objective = self.objectives[order.target_id]
                unit.zone_id = objective.zone_id
                objective.status = ObjectiveStatus.SECURED
                produced.append(
                    self._event(
                        kind="objective-completed",
                        command_id=command_id,
                        data={
                            "unit_id": unit.entity_id,
                            "target_id": objective.objective_id,
                        },
                    )
                )
            elif order.op == RecallCommand.OP.value:
                unit.zone_id = order.target_id or "staging"
                produced.append(
                    self._event(
                        kind="movement-completed",
                        command_id=command_id,
                        data={
                            "unit_id": unit.entity_id,
                            "target_id": unit.zone_id,
                        },
                    )
                )
            else:
                raise RuntimeError(f"unsupported pending order op: {order.op}")
            self._finish_order(order, unit)

        return tuple(produced)

    def private_snapshot(self) -> JsonObject:
        return {
            "scenario_id": self.blueprint.scenario.identity.scenario_id,
            "seed": self.blueprint.seed,
            "tick": self.tick,
            "generation": self.generation,
            "private_facts": self.blueprint.private_facts,
            "routes": {
                route_id: {
                    "origin_zone": route.origin_zone,
                    "destination_zone": route.destination_zone,
                    "travel_ticks": route.travel_ticks,
                    "blocked": route.blocked,
                    "hazard_period": route.hazard_period,
                }
                for route_id, route in sorted(self._routes.items())
            },
            "units": {
                unit_id: {
                    "archetype_id": unit.archetype_id,
                    "zone_id": unit.zone_id,
                    "energy": unit.energy,
                    "status": unit.status.value,
                    "current_order_id": unit.current_order_id,
                }
                for unit_id, unit in sorted(self.units.items())
            },
            "objectives": {
                objective_id: {
                    "zone_id": objective.zone_id,
                    "status": objective.status.value,
                }
                for objective_id, objective in sorted(self.objectives.items())
            },
            "orders": {
                order_id: {
                    **asdict(order),
                    "data": order.data,
                }
                for order_id, order in sorted(self.orders.items())
            },
            "discovered_routes": sorted(self.discovered_routes),
        }

    def state_hash(self) -> str:
        return content_hash(self.private_snapshot())

    def event_hash(self) -> str:
        return content_hash([event.to_dict() for event in self.events])

    def world_private_reference(self) -> WorldPrivateReference:
        return WorldPrivateReference(
            state_id=(f"{self.blueprint.scenario.identity.scenario_id}:g{self.generation}"),
            scenario=self.blueprint.scenario.identity,
            state_hash=self.state_hash(),
            generation=self.generation,
            secret_ids=tuple(sorted(self.blueprint.private_facts)),
        )

    def commander_observation(self, *, turn_id: int) -> CommanderObservation:
        known_routes: JsonObject = {}
        for route_id in sorted(self.discovered_routes):
            route = self._routes[route_id]
            known_routes[route_id] = {
                "origin_zone": route.origin_zone,
                "destination_zone": route.destination_zone,
                "blocked": route.blocked,
            }
        facts: JsonObject = {
            "tick": self.tick,
            "units": {
                unit_id: {
                    "zone_id": unit.zone_id,
                    "status": unit.status.value,
                    "energy": unit.energy,
                }
                for unit_id, unit in sorted(self.units.items())
                if unit.status is not UnitStatus.LOST
            },
            "objectives": {
                objective_id: {"status": objective.status.value}
                for objective_id, objective in sorted(self.objectives.items())
            },
            "known_routes": known_routes,
        }
        return CommanderObservation(
            turn_id=turn_id,
            world_state_id=self.world_private_reference().state_id,
            visible_entities=tuple(
                sorted(
                    [
                        *(
                            unit_id
                            for unit_id, unit in self.units.items()
                            if unit.status is not UnitStatus.LOST
                        ),
                        *self.objectives,
                    ]
                )
            ),
            objective_ids=tuple(sorted(self.objectives)),
            event_ids=tuple(event.event_id for event in self.events[-8:]),
            facts=facts,
        )

    def player_observation(self, *, turn_id: int) -> PlayerObservation:
        facts: JsonObject = {
            "tick": self.tick,
            "units": {
                unit_id: {
                    "zone_id": unit.zone_id,
                    "status": unit.status.value,
                }
                for unit_id, unit in sorted(self.units.items())
                if unit.status is not UnitStatus.LOST
            },
            "objectives": {
                objective_id: {"status": objective.status.value}
                for objective_id, objective in sorted(self.objectives.items())
            },
        }
        return PlayerObservation(
            turn_id=turn_id,
            visible_entities=tuple(
                sorted(
                    [
                        *(
                            unit_id
                            for unit_id, unit in self.units.items()
                            if unit.status is not UnitStatus.LOST
                        ),
                        *self.objectives,
                    ]
                )
            ),
            event_ids=tuple(event.event_id for event in self.events[-4:]),
            facts=facts,
        )
