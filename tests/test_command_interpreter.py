from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    CommandInterpreter,
    DispatchReceipt,
    EntitySnapshot,
    ErrorCode,
    HoldCommand,
    TypedCommand,
    ValidationFailure,
)
from techrotic_training_triumvirate.schemas import CommandEnvelope, JsonObject


@dataclass
class FakeWorld:
    observation_generation: int = 7
    entities: dict[str, EntitySnapshot] = field(default_factory=dict)
    targets: set[str] = field(default_factory=lambda: {"relay", "staging"})
    precondition_failure: ValidationFailure | None = None
    resource_failure: ValidationFailure | None = None
    conflict_failure: ValidationFailure | None = None
    dispatched: list[TypedCommand] = field(default_factory=list)

    def entity(self, entity_id: str) -> EntitySnapshot | None:
        return self.entities.get(entity_id)

    def target_exists(self, target_id: str) -> bool:
        return target_id in self.targets

    def check_preconditions(
        self, command: TypedCommand
    ) -> ValidationFailure | None:
        del command
        return self.precondition_failure

    def check_resources(
        self, command: TypedCommand
    ) -> ValidationFailure | None:
        del command
        return self.resource_failure

    def check_order_conflict(
        self, command: TypedCommand
    ) -> ValidationFailure | None:
        del command
        return self.conflict_failure

    def dispatch(self, command: TypedCommand) -> DispatchReceipt:
        self.dispatched.append(command)
        return DispatchReceipt(
            event_id=f"dispatch-{len(self.dispatched)}",
            tick=12,
            data={"world_generation": self.observation_generation},
        )


def capable_world() -> FakeWorld:
    capabilities = frozenset(
        {
            "command.assign_objective",
            "command.set_constraints",
            "command.coordinate",
            "command.order_control",
        }
    )
    return FakeWorld(
        entities={
            "unit-a": EntitySnapshot("unit-a", True, capabilities),
            "unit-b": EntitySnapshot("unit-b", True, capabilities),
        }
    )


def assign_command(
    *,
    generation: int = 7,
    target: str = "relay",
) -> AssignObjectiveCommand:
    return AssignObjectiveCommand(
        command_id="cmd-assign",
        observation_generation=generation,
        unit_id="unit-a",
        objective_kind="flank",
        target_id=target,
        approach="north",
        constraints=("avoid:flooded",),
    )


def assert_rejected(
    world: FakeWorld,
    envelope: CommandEnvelope,
    code: ErrorCode,
) -> None:
    outcome = CommandInterpreter().interpret(envelope, world)

    assert outcome.result.accepted is False
    assert outcome.result.code == code.value
    assert outcome.dispatch_event is None
    assert world.dispatched == []


def test_accepted_command_dispatches_but_does_not_claim_execution_success() -> None:
    world = capable_world()

    outcome = CommandInterpreter().interpret(
        assign_command().to_envelope(),
        world,
    )

    assert outcome.result.accepted is True
    assert outcome.result.code == "OK"
    assert len(world.dispatched) == 1
    assert outcome.dispatch_event is not None
    assert outcome.dispatch_event.kind == "command-dispatched"
    assert outcome.dispatch_event.related_command_ids == ("cmd-assign",)
    assert outcome.dispatch_event.data["accepted_for_execution"] is True
    assert "execution_success" not in outcome.dispatch_event.data
    assert "execution_success" not in outcome.result.detail


def test_same_world_and_command_produce_same_result_and_event() -> None:
    command = assign_command().to_envelope()

    first = CommandInterpreter().interpret(command, capable_world())
    second = CommandInterpreter().interpret(command, capable_world())

    assert first == second


def test_schema_failure_never_dispatches() -> None:
    world = capable_world()
    bad = CommandEnvelope(
        command_id="bad",
        protocol_version="ttt-command-v1",
        body={
            "op": "hold",
            "observation_generation": 7,
            "unit_id": "unit-a",
            "exec": "/bin/sh",
        },
    )

    assert_rejected(world, bad, ErrorCode.SCHEMA_INVALID)


def test_unknown_entity_rejects_without_dispatch() -> None:
    world = capable_world()
    command = HoldCommand("cmd-hold", 7, "missing")

    assert_rejected(world, command.to_envelope(), ErrorCode.ENTITY_UNKNOWN)


def test_unavailable_entity_rejects_without_dispatch() -> None:
    world = capable_world()
    original = world.entities["unit-a"]
    world.entities["unit-a"] = EntitySnapshot(
        original.entity_id,
        False,
        original.capabilities,
    )
    command = HoldCommand("cmd-hold", 7, "unit-a")

    assert_rejected(world, command.to_envelope(), ErrorCode.ENTITY_UNAVAILABLE)


def test_capability_mismatch_rejects_without_dispatch() -> None:
    world = capable_world()
    world.entities["unit-a"] = EntitySnapshot(
        "unit-a",
        True,
        frozenset({"command.order_control"}),
    )

    assert_rejected(
        world,
        assign_command().to_envelope(),
        ErrorCode.CAPABILITY_MISMATCH,
    )


def test_invalid_target_rejects_without_dispatch() -> None:
    world = capable_world()

    assert_rejected(
        world,
        assign_command(target="unknown-target").to_envelope(),
        ErrorCode.TARGET_INVALID,
    )


@pytest.mark.parametrize(
    ("attribute", "code", "detail"),
    [
        (
            "precondition_failure",
            ErrorCode.PRECONDITION_FAILED,
            {"reason": "support missing"},
        ),
        (
            "resource_failure",
            ErrorCode.RESOURCE_EXHAUSTED,
            {"resource": "fuel"},
        ),
        (
            "conflict_failure",
            ErrorCode.ORDER_CONFLICT,
            {"order_id": "order-existing"},
        ),
    ],
)
def test_world_validation_failures_never_dispatch(
    attribute: str,
    code: ErrorCode,
    detail: JsonObject,
) -> None:
    world = capable_world()
    setattr(world, attribute, ValidationFailure(detail))

    assert_rejected(world, assign_command().to_envelope(), code)


def test_stale_observation_rejects_before_world_validation() -> None:
    world = capable_world()

    assert_rejected(
        world,
        assign_command(generation=6).to_envelope(),
        ErrorCode.STALE_OBSERVATION,
    )
