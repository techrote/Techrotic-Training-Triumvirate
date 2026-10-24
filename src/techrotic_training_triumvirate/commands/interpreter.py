"""Deterministic command admission and dispatch interpreter."""

from __future__ import annotations

from dataclasses import dataclass

from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    CommandEnvelope,
    InterpreterResult,
    JsonObject,
)

from .model import (
    AssignObjectiveCommand,
    CancelCommand,
    CoordinateCommand,
    ErrorCode,
    HoldCommand,
    InspectCommand,
    RecallCommand,
    RequestStatusCommand,
    SetConstraintsCommand,
    TransmitCommand,
    TypedCommand,
    command_operation,
)
from .parser import CommandParseError, parse_command_envelope
from .world import WorldAdapter


@dataclass(frozen=True, slots=True)
class InterpreterOutcome:
    result: InterpreterResult
    dispatch_event: AuthoritativeEvent | None
    command: TypedCommand | None


def _rejected(
    command_id: str,
    code: ErrorCode,
    detail: JsonObject,
    *,
    command: TypedCommand | None = None,
) -> InterpreterOutcome:
    return InterpreterOutcome(
        result=InterpreterResult(
            command_id=command_id,
            accepted=False,
            code=code.value,
            detail=detail,
        ),
        dispatch_event=None,
        command=command,
    )


def _entity_ids(command: TypedCommand) -> tuple[str, ...]:
    if isinstance(command, InspectCommand):
        return (command.entity_id,)
    if isinstance(
        command,
        (
            AssignObjectiveCommand,
            SetConstraintsCommand,
            HoldCommand,
            CancelCommand,
            RecallCommand,
        ),
    ):
        return (command.unit_id,)
    if isinstance(command, CoordinateCommand):
        return command.unit_ids
    if isinstance(command, TransmitCommand):
        return command.recipients
    if isinstance(command, RequestStatusCommand):
        return command.entity_ids
    raise AssertionError(f"unhandled command type: {type(command).__name__}")


def _target_id(command: TypedCommand) -> str | None:
    if isinstance(command, AssignObjectiveCommand):
        return command.target_id
    if isinstance(command, RecallCommand):
        return command.destination_id
    if isinstance(command, CoordinateCommand):
        return command.objective_id
    return None


def _required_capability(command: TypedCommand) -> str | None:
    if isinstance(command, AssignObjectiveCommand):
        return "command.assign_objective"
    if isinstance(command, SetConstraintsCommand):
        return "command.set_constraints"
    if isinstance(command, CoordinateCommand):
        return "command.coordinate"
    if isinstance(command, (HoldCommand, CancelCommand, RecallCommand)):
        return "command.order_control"
    return None


class CommandInterpreter:
    """Validate and dispatch bounded high-level commands deterministically."""

    def interpret(
        self,
        envelope: CommandEnvelope,
        world: WorldAdapter,
    ) -> InterpreterOutcome:
        try:
            command = parse_command_envelope(envelope)
        except CommandParseError as exc:
            return _rejected(
                envelope.command_id,
                exc.code,
                {"message": exc.detail},
            )

        if command.observation_generation != world.observation_generation:
            return _rejected(
                command.command_id,
                ErrorCode.STALE_OBSERVATION,
                {
                    "command_generation": command.observation_generation,
                    "world_generation": world.observation_generation,
                },
                command=command,
            )

        entities = []
        for entity_id in _entity_ids(command):
            entity = world.entity(entity_id)
            if entity is None:
                return _rejected(
                    command.command_id,
                    ErrorCode.ENTITY_UNKNOWN,
                    {"entity_id": entity_id},
                    command=command,
                )
            if not entity.available:
                return _rejected(
                    command.command_id,
                    ErrorCode.ENTITY_UNAVAILABLE,
                    {"entity_id": entity_id},
                    command=command,
                )
            entities.append(entity)

        target_id = _target_id(command)
        if target_id is not None and not world.target_exists(target_id):
            return _rejected(
                command.command_id,
                ErrorCode.TARGET_INVALID,
                {"target_id": target_id},
                command=command,
            )

        required_capability = _required_capability(command)
        if required_capability is not None:
            for entity in entities:
                if required_capability not in entity.capabilities:
                    return _rejected(
                        command.command_id,
                        ErrorCode.CAPABILITY_MISMATCH,
                        {
                            "entity_id": entity.entity_id,
                            "required_capability": required_capability,
                        },
                        command=command,
                    )

        precondition_failure = world.check_preconditions(command)
        if precondition_failure is not None:
            return _rejected(
                command.command_id,
                ErrorCode.PRECONDITION_FAILED,
                precondition_failure.detail,
                command=command,
            )

        resource_failure = world.check_resources(command)
        if resource_failure is not None:
            return _rejected(
                command.command_id,
                ErrorCode.RESOURCE_EXHAUSTED,
                resource_failure.detail,
                command=command,
            )

        conflict = world.check_order_conflict(command)
        if conflict is not None:
            return _rejected(
                command.command_id,
                ErrorCode.ORDER_CONFLICT,
                conflict.detail,
                command=command,
            )

        receipt = world.dispatch(command)
        operation = command_operation(command).value
        event_data: JsonObject = {
            "op": operation,
            "accepted_for_execution": True,
            **receipt.data,
        }
        event = AuthoritativeEvent(
            event_id=receipt.event_id,
            kind="command-dispatched",
            tick=receipt.tick,
            related_command_ids=(command.command_id,),
            data=event_data,
        )
        return InterpreterOutcome(
            result=InterpreterResult(
                command_id=command.command_id,
                accepted=True,
                code="OK",
                detail={
                    "op": operation,
                    "dispatch_event_id": receipt.event_id,
                    "accepted_for_execution": True,
                },
            ),
            dispatch_event=event,
            command=command,
        )
