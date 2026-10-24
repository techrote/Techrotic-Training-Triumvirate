"""Typed, bounded TTT command protocol v1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from techrotic_training_triumvirate.schemas import CommandEnvelope, JsonObject


COMMAND_PROTOCOL_VERSION = "ttt-command-v1"


class Operation(str, Enum):
    INSPECT = "inspect"
    ASSIGN_OBJECTIVE = "assign_objective"
    SET_CONSTRAINTS = "set_constraints"
    COORDINATE = "coordinate"
    HOLD = "hold"
    CANCEL = "cancel"
    RECALL = "recall"
    TRANSMIT = "transmit"
    REQUEST_STATUS = "request_status"


class ErrorCode(str, Enum):
    SCHEMA_INVALID = "SCHEMA_INVALID"
    PROTOCOL_UNSUPPORTED = "PROTOCOL_UNSUPPORTED"
    ENTITY_UNKNOWN = "ENTITY_UNKNOWN"
    ENTITY_UNAVAILABLE = "ENTITY_UNAVAILABLE"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    TARGET_INVALID = "TARGET_INVALID"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    ORDER_CONFLICT = "ORDER_CONFLICT"


@dataclass(frozen=True, slots=True)
class BaseCommand:
    command_id: str
    observation_generation: int
    OP: ClassVar[Operation]

    def body(self) -> JsonObject:
        raise NotImplementedError

    def to_envelope(self) -> CommandEnvelope:
        return CommandEnvelope(
            command_id=self.command_id,
            protocol_version=COMMAND_PROTOCOL_VERSION,
            body=self.body(),
        )


@dataclass(frozen=True, slots=True)
class InspectCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.INSPECT
    entity_id: str
    fields: tuple[str, ...]

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "entity_id": self.entity_id,
            "fields": list(self.fields),
        }


@dataclass(frozen=True, slots=True)
class AssignObjectiveCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.ASSIGN_OBJECTIVE
    unit_id: str
    objective_kind: str
    target_id: str
    approach: str | None
    constraints: tuple[str, ...]

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "unit_id": self.unit_id,
            "objective_kind": self.objective_kind,
            "target_id": self.target_id,
            "approach": self.approach,
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True, slots=True)
class SetConstraintsCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.SET_CONSTRAINTS
    unit_id: str
    constraints: JsonObject

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "unit_id": self.unit_id,
            "constraints": self.constraints,
        }


@dataclass(frozen=True, slots=True)
class CoordinateCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.COORDINATE
    unit_ids: tuple[str, ...]
    trigger: str
    objective_id: str | None

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "unit_ids": list(self.unit_ids),
            "trigger": self.trigger,
            "objective_id": self.objective_id,
        }


@dataclass(frozen=True, slots=True)
class HoldCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.HOLD
    unit_id: str

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "unit_id": self.unit_id,
        }


@dataclass(frozen=True, slots=True)
class CancelCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.CANCEL
    unit_id: str
    order_id: str | None

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "unit_id": self.unit_id,
            "order_id": self.order_id,
        }


@dataclass(frozen=True, slots=True)
class RecallCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.RECALL
    unit_id: str
    destination_id: str | None

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "unit_id": self.unit_id,
            "destination_id": self.destination_id,
        }


@dataclass(frozen=True, slots=True)
class TransmitCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.TRANSMIT
    recipients: tuple[str, ...]
    channel: str
    message: str

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "recipients": list(self.recipients),
            "channel": self.channel,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class RequestStatusCommand(BaseCommand):
    OP: ClassVar[Operation] = Operation.REQUEST_STATUS
    entity_ids: tuple[str, ...]

    def body(self) -> JsonObject:
        return {
            "op": self.OP.value,
            "observation_generation": self.observation_generation,
            "entity_ids": list(self.entity_ids),
        }


TypedCommand = (
    InspectCommand
    | AssignObjectiveCommand
    | SetConstraintsCommand
    | CoordinateCommand
    | HoldCommand
    | CancelCommand
    | RecallCommand
    | TransmitCommand
    | RequestStatusCommand
)


def command_operation(command: TypedCommand) -> Operation:
    return command.OP
