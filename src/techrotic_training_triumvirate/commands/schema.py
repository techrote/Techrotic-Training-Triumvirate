"""Machine-readable structural schema for TTT command protocol v1."""

from __future__ import annotations

from typing import Any

from .model import COMMAND_PROTOCOL_VERSION


def _base_properties(op: str) -> dict[str, Any]:
    return {
        "op": {"const": op},
        "observation_generation": {"type": "integer", "minimum": 0},
    }


def _body(
    op: str,
    extra: dict[str, Any],
) -> dict[str, Any]:
    properties = {**_base_properties(op), **extra}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def command_schema() -> dict[str, Any]:
    """Return JSON Schema 2020-12 for model-emitted command bodies."""
    nonempty_string = {"type": "string", "minLength": 1}
    optional_string = {
        "anyOf": [nonempty_string, {"type": "null"}],
    }
    nonempty_string_array = {
        "type": "array",
        "minItems": 1,
        "uniqueItems": True,
        "items": nonempty_string,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://techrote.github.io/Techrotic-Training-Triumvirate/"
            "command/ttt-command-v1.json"
        ),
        "title": f"TTT command body protocol {COMMAND_PROTOCOL_VERSION}",
        "oneOf": [
            _body(
                "inspect",
                {
                    "entity_id": nonempty_string,
                    "fields": nonempty_string_array,
                },
            ),
            _body(
                "assign_objective",
                {
                    "unit_id": nonempty_string,
                    "objective_kind": nonempty_string,
                    "target_id": nonempty_string,
                    "approach": optional_string,
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            ),
            _body(
                "set_constraints",
                {
                    "unit_id": nonempty_string,
                    "constraints": {
                        "type": "object",
                        "minProperties": 1,
                    },
                },
            ),
            _body(
                "coordinate",
                {
                    "unit_ids": nonempty_string_array,
                    "trigger": nonempty_string,
                    "objective_id": optional_string,
                },
            ),
            _body("hold", {"unit_id": nonempty_string}),
            _body(
                "cancel",
                {
                    "unit_id": nonempty_string,
                    "order_id": optional_string,
                },
            ),
            _body(
                "recall",
                {
                    "unit_id": nonempty_string,
                    "destination_id": optional_string,
                },
            ),
            _body(
                "transmit",
                {
                    "recipients": nonempty_string_array,
                    "channel": nonempty_string,
                    "message": nonempty_string,
                },
            ),
            _body(
                "request_status",
                {"entity_ids": nonempty_string_array},
            ),
        ],
    }
