"""Strict parser from JSON-compatible model output to typed TTT commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from techrotic_training_triumvirate.schemas import CommandEnvelope, JsonObject
from techrotic_training_triumvirate.schemas.base import (
    require_exact_keys,
    require_int,
    require_json_object,
    require_optional_str,
    require_str,
    require_str_tuple,
)

from .model import (
    COMMAND_PROTOCOL_VERSION,
    AssignObjectiveCommand,
    CancelCommand,
    CoordinateCommand,
    ErrorCode,
    HoldCommand,
    InspectCommand,
    Operation,
    RecallCommand,
    RequestStatusCommand,
    SetConstraintsCommand,
    TransmitCommand,
    TypedCommand,
)


@dataclass(frozen=True, slots=True)
class CommandParseError(ValueError):
    code: ErrorCode
    detail: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.detail}"


def _nonempty(value: object, *, field: str) -> str:
    result = require_str(value, field=field)
    if not result.strip():
        raise ValueError(f"{field} must not be empty")
    return result


def _nonempty_tuple(value: object, *, field: str) -> tuple[str, ...]:
    result = require_str_tuple(value, field=field)
    if not result:
        raise ValueError(f"{field} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must not contain duplicates")
    if any(not item.strip() for item in result):
        raise ValueError(f"{field} entries must not be empty")
    return result


def _generation(body: JsonObject) -> int:
    generation = require_int(
        body["observation_generation"], field="observation_generation"
    )
    if generation < 0:
        raise ValueError("observation_generation must be non-negative")
    return generation


def _parse_body(command_id: str, body: JsonObject) -> TypedCommand:
    op_text = require_str(body.get("op"), field="op")
    try:
        op = Operation(op_text)
    except ValueError as exc:
        raise ValueError(f"unsupported operation: {op_text}") from exc

    common = {"op", "observation_generation"}
    if op is Operation.INSPECT:
        require_exact_keys(
            body,
            required=common | {"entity_id", "fields"},
            where="command body",
        )
        return InspectCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            entity_id=_nonempty(body["entity_id"], field="entity_id"),
            fields=_nonempty_tuple(body["fields"], field="fields"),
        )

    if op is Operation.ASSIGN_OBJECTIVE:
        require_exact_keys(
            body,
            required=common
            | {
                "unit_id",
                "objective_kind",
                "target_id",
                "approach",
                "constraints",
            },
            where="command body",
        )
        approach = require_optional_str(body["approach"], field="approach")
        if approach is not None and not approach.strip():
            raise ValueError("approach must be null or non-empty")
        return AssignObjectiveCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            unit_id=_nonempty(body["unit_id"], field="unit_id"),
            objective_kind=_nonempty(body["objective_kind"], field="objective_kind"),
            target_id=_nonempty(body["target_id"], field="target_id"),
            approach=approach,
            constraints=require_str_tuple(body["constraints"], field="constraints"),
        )

    if op is Operation.SET_CONSTRAINTS:
        require_exact_keys(
            body,
            required=common | {"unit_id", "constraints"},
            where="command body",
        )
        constraints = require_json_object(body["constraints"], field="constraints")
        if not constraints:
            raise ValueError("constraints must not be empty")
        return SetConstraintsCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            unit_id=_nonempty(body["unit_id"], field="unit_id"),
            constraints=constraints,
        )

    if op is Operation.COORDINATE:
        require_exact_keys(
            body,
            required=common | {"unit_ids", "trigger", "objective_id"},
            where="command body",
        )
        objective_id = require_optional_str(body["objective_id"], field="objective_id")
        if objective_id is not None and not objective_id.strip():
            raise ValueError("objective_id must be null or non-empty")
        return CoordinateCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            unit_ids=_nonempty_tuple(body["unit_ids"], field="unit_ids"),
            trigger=_nonempty(body["trigger"], field="trigger"),
            objective_id=objective_id,
        )

    if op is Operation.HOLD:
        require_exact_keys(
            body,
            required=common | {"unit_id"},
            where="command body",
        )
        return HoldCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            unit_id=_nonempty(body["unit_id"], field="unit_id"),
        )

    if op is Operation.CANCEL:
        require_exact_keys(
            body,
            required=common | {"unit_id", "order_id"},
            where="command body",
        )
        order_id = require_optional_str(body["order_id"], field="order_id")
        return CancelCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            unit_id=_nonempty(body["unit_id"], field="unit_id"),
            order_id=order_id,
        )

    if op is Operation.RECALL:
        require_exact_keys(
            body,
            required=common | {"unit_id", "destination_id"},
            where="command body",
        )
        destination_id = require_optional_str(
            body["destination_id"], field="destination_id"
        )
        return RecallCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            unit_id=_nonempty(body["unit_id"], field="unit_id"),
            destination_id=destination_id,
        )

    if op is Operation.TRANSMIT:
        require_exact_keys(
            body,
            required=common | {"recipients", "channel", "message"},
            where="command body",
        )
        return TransmitCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            recipients=_nonempty_tuple(body["recipients"], field="recipients"),
            channel=_nonempty(body["channel"], field="channel"),
            message=_nonempty(body["message"], field="message"),
        )

    if op is Operation.REQUEST_STATUS:
        require_exact_keys(
            body,
            required=common | {"entity_ids"},
            where="command body",
        )
        return RequestStatusCommand(
            command_id=command_id,
            observation_generation=_generation(body),
            entity_ids=_nonempty_tuple(body["entity_ids"], field="entity_ids"),
        )

    raise AssertionError(f"unhandled operation: {op}")


def parse_command_envelope(envelope: CommandEnvelope) -> TypedCommand:
    """Parse one canonical envelope, refusing protocol/schema drift."""
    if envelope.protocol_version != COMMAND_PROTOCOL_VERSION:
        raise CommandParseError(
            ErrorCode.PROTOCOL_UNSUPPORTED,
            (
                f"unsupported command protocol {envelope.protocol_version!r}; "
                f"expected {COMMAND_PROTOCOL_VERSION!r}"
            ),
        )
    try:
        return _parse_body(envelope.command_id, envelope.body)
    except (KeyError, TypeError, ValueError) as exc:
        raise CommandParseError(ErrorCode.SCHEMA_INVALID, str(exc)) from exc


def parse_model_command(
    value: str | JsonObject,
    *,
    command_id: str,
    protocol_version: str = COMMAND_PROTOCOL_VERSION,
) -> TypedCommand:
    """Parse a model-emitted command body from JSON text or an object.

    The caller assigns command identity; model output cannot select a host
    executable, callback, or arbitrary Python function.
    """
    raw: object = value
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CommandParseError(
                ErrorCode.SCHEMA_INVALID,
                f"invalid JSON: {exc.msg}",
            ) from exc
    try:
        body = require_json_object(raw, field="command body")
    except (TypeError, ValueError) as exc:
        raise CommandParseError(ErrorCode.SCHEMA_INVALID, str(exc)) from exc
    envelope = CommandEnvelope(
        command_id=command_id,
        protocol_version=protocol_version,
        body=body,
    )
    return parse_command_envelope(envelope)
