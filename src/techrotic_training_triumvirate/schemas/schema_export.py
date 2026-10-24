"""Machine-readable JSON Schema bundle for canonical TTT record envelopes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .base import registered_record_types


_STRING: dict[str, Any] = {"type": "string"}
_INTEGER: dict[str, Any] = {"type": "integer"}
_BOOLEAN: dict[str, Any] = {"type": "boolean"}
_OBJECT: dict[str, Any] = {"type": "object"}


def _array(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _ref(schema_name: str) -> dict[str, Any]:
    return {"$ref": f"#/$defs/{schema_name}"}


def _payload_schema(
    properties: dict[str, Any],
    *,
    required: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    required_names = list(required if required is not None else properties)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required_names,
        "properties": properties,
    }


_PAYLOAD_SCHEMAS: dict[str, dict[str, Any]] = {
    "ttt.scenario_identity": _payload_schema(
        {
            "scenario_id": _STRING,
            "family": _STRING,
            "generator": _STRING,
            "generator_version": _STRING,
            "seed": _INTEGER,
        }
    ),
    "ttt.capability": _payload_schema(
        {
            "capability_id": _STRING,
            "parameters": _OBJECT,
        }
    ),
    "ttt.entity": _payload_schema(
        {
            "entity_id": _STRING,
            "kind": _STRING,
            "capabilities": _array(_ref("ttt.capability")),
            "tags": _array(_STRING),
        }
    ),
    "ttt.scenario": _payload_schema(
        {
            "identity": _ref("ttt.scenario_identity"),
            "entities": _array(_ref("ttt.entity")),
            "objective_ids": _array(_STRING),
            "topology_refs": _array(_STRING),
            "metadata": _OBJECT,
        }
    ),
    "ttt.world_private_reference": _payload_schema(
        {
            "state_id": _STRING,
            "scenario": _ref("ttt.scenario_identity"),
            "state_hash": _STRING,
            "generation": _INTEGER,
            "secret_ids": _array(_STRING),
        }
    ),
    "ttt.commander_observation": _payload_schema(
        {
            "turn_id": _INTEGER,
            "world_state_id": _STRING,
            "visible_entities": _array(_STRING),
            "objective_ids": _array(_STRING),
            "event_ids": _array(_STRING),
            "facts": _OBJECT,
        }
    ),
    "ttt.commander_private_context": _payload_schema(
        {
            "commander_id": _STRING,
            "goals": _array(_STRING),
            "secret_ids": _array(_STRING),
            "beliefs": _OBJECT,
            "memory_refs": _array(_STRING),
        }
    ),
    "ttt.player_observation": _payload_schema(
        {
            "turn_id": _INTEGER,
            "visible_entities": _array(_STRING),
            "event_ids": _array(_STRING),
            "facts": _OBJECT,
        }
    ),
    "ttt.player_intercept": _payload_schema(
        {
            "intercept_id": _STRING,
            "source_event_ids": _array(_STRING),
            "payload": _OBJECT,
            "is_deception": _BOOLEAN,
            "deception_event_id": _nullable(_STRING),
        }
    ),
    "ttt.persona": _payload_schema(
        {
            "persona_id": _STRING,
            "archetype": _STRING,
            "traits": _OBJECT,
            "speech_constraints": _array(_STRING),
            "doctrine": _OBJECT,
            "secret_ids": _array(_STRING),
            "tactical_biases": _OBJECT,
        }
    ),
    "ttt.command_envelope": _payload_schema(
        {
            "command_id": _STRING,
            "protocol_version": _STRING,
            "body": _OBJECT,
        }
    ),
    "ttt.communication": _payload_schema(
        {
            "communication_id": _STRING,
            "channel": _STRING,
            "text": _STRING,
            "recipients": _array(_STRING),
        }
    ),
    "ttt.assistant_action": _payload_schema(
        {
            "commands": _array(_ref("ttt.command_envelope")),
            "communications": _array(_ref("ttt.communication")),
        }
    ),
    "ttt.interpreter_result": _payload_schema(
        {
            "command_id": _STRING,
            "accepted": _BOOLEAN,
            "code": _STRING,
            "detail": _OBJECT,
        }
    ),
    "ttt.authoritative_event": _payload_schema(
        {
            "event_id": _STRING,
            "kind": _STRING,
            "tick": _INTEGER,
            "related_command_ids": _array(_STRING),
            "data": _OBJECT,
        }
    ),
    "ttt.evaluation_annotations": _payload_schema(
        {
            "labels": _OBJECT,
            "evaluator_only": _OBJECT,
        }
    ),
    "ttt.turn": _payload_schema(
        {
            "turn_id": _INTEGER,
            "observation": _ref("ttt.commander_observation"),
            "commander_private_context": _ref(
                "ttt.commander_private_context"
            ),
            "assistant_action": _ref("ttt.assistant_action"),
            "interpreter_results": _array(_ref("ttt.interpreter_result")),
            "world_events": _array(_ref("ttt.authoritative_event")),
            "next_observation": _ref("ttt.commander_observation"),
            "player_observation": _ref("ttt.player_observation"),
            "player_intercepts": _array(_ref("ttt.player_intercept")),
            "annotations": _ref("ttt.evaluation_annotations"),
        }
    ),
    "ttt.source_provenance": _payload_schema(
        {
            "source_id": _STRING,
            "source_class": _STRING,
            "uri": _nullable(_STRING),
            "revision": _nullable(_STRING),
            "license_id": _nullable(_STRING),
            "source_content_hash": _nullable(_STRING),
            "metadata": _OBJECT,
        }
    ),
    "ttt.run_manifest": _payload_schema(
        {
            "run_id": _STRING,
            "git_commit": _STRING,
            "schema_versions": _OBJECT,
            "seeds": _OBJECT,
            "generator_config": _OBJECT,
            "source_refs": _array(_STRING),
            "parent_run_ids": _array(_STRING),
            "artifact_hashes": _OBJECT,
            "command_line": _array(_STRING),
            "runtime": _OBJECT,
        }
    ),
    "ttt.episode": _payload_schema(
        {
            "episode_id": _STRING,
            "scenario": _ref("ttt.scenario"),
            "persona": _ref("ttt.persona"),
            "initial_world": _ref("ttt.world_private_reference"),
            "turns": _array(_ref("ttt.turn")),
            "final_world_hash": _STRING,
            "run_id": _STRING,
        }
    ),
}


def schema_bundle() -> dict[str, Any]:
    """Return a JSON Schema 2020-12 bundle for all registered v1 records."""
    registered = registered_record_types()
    missing = set(registered) - set(_PAYLOAD_SCHEMAS)
    extra = set(_PAYLOAD_SCHEMAS) - set(registered)
    if missing or extra:
        raise RuntimeError(
            "schema export registry mismatch: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )

    definitions: dict[str, Any] = {}
    for name, record_type in registered.items():
        definitions[name] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema", "schema_version", "payload"],
            "properties": {
                "schema": {"const": name},
                "schema_version": {"const": record_type.SCHEMA_VERSION},
                "payload": deepcopy(_PAYLOAD_SCHEMAS[name]),
            },
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://techrote.github.io/Techrotic-Training-Triumvirate/schema/v1/bundle.json",
        "title": "Techrotic Training Triumvirate canonical schema bundle v1",
        "oneOf": [_ref(name) for name in sorted(definitions)],
        "$defs": definitions,
    }
