"""Deterministic simulator-aware correction oracle for TTT-010."""

from __future__ import annotations

from typing import Protocol

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    RequestStatusCommand,
)
from techrotic_training_triumvirate.schemas import AssistantAction
from techrotic_training_triumvirate.world import WorldBlueprint

from .model import FailurePoint


class CorrectionOracle(Protocol):
    """Privileged label generator; never part of the student-visible surface."""

    @property
    def oracle_id(self) -> str: ...

    def propose(
        self,
        failure: FailurePoint,
        *,
        observation_generation: int,
        blueprint: WorldBlueprint,
        max_alternatives: int,
    ) -> tuple[AssistantAction, ...]: ...


class DeterministicRecoveryOracle:
    """Use explicit abstract-simulator knowledge to produce admissible repairs."""

    @property
    def oracle_id(self) -> str:
        return "abstract-simulator-oracle-v1"

    def propose(
        self,
        failure: FailurePoint,
        *,
        observation_generation: int,
        blueprint: WorldBlueprint,
        max_alternatives: int,
    ) -> tuple[AssistantAction, ...]:
        if max_alternatives < 1:
            raise ValueError("max_alternatives must be positive")

        attempted = (
            failure.action.commands[0] if len(failure.action.commands) == 1 else None
        )
        attempted_body = attempted.body if attempted is not None else {}
        unit_ids = tuple(unit.entity_id for unit in blueprint.units)
        objective_ids = tuple(item.objective_id for item in blueprint.objectives)
        if not unit_ids or not objective_ids:
            return ()

        preferred_unit = attempted_body.get("unit_id")
        unit_id = (
            preferred_unit
            if isinstance(preferred_unit, str) and preferred_unit in unit_ids
            else unit_ids[0]
        )
        if failure.code == "CAPABILITY_MISMATCH" and len(unit_ids) > 1:
            unit_id = unit_ids[1]

        preferred_target = attempted_body.get("target_id")
        target_id = (
            preferred_target
            if isinstance(preferred_target, str)
            and preferred_target in objective_ids
            else objective_ids[0]
        )

        actions: list[AssistantAction] = []
        if failure.code not in {"TARGET_STATE_CHANGED", "ORDER_CONFLICT"}:
            open_routes = tuple(
                route.route_id
                for route in blueprint.routes
                if not route.blocked
            )
            for index, route_id in enumerate(open_routes):
                command = AssignObjectiveCommand(
                    command_id=f"{failure.attempt_id}:repair:{index:02d}",
                    observation_generation=observation_generation,
                    unit_id=unit_id,
                    objective_kind="secure",
                    target_id=target_id,
                    approach=route_id,
                    constraints=(),
                )
                actions.append(
                    AssistantAction(
                        commands=(command.to_envelope(),),
                        communications=(),
                    )
                )

        status = RequestStatusCommand(
            command_id=f"{failure.attempt_id}:repair:status",
            observation_generation=observation_generation,
            entity_ids=(unit_id, target_id),
        )
        actions.append(
            AssistantAction(
                commands=(status.to_envelope(),),
                communications=(),
            )
        )
        return tuple(actions[:max_alternatives])
