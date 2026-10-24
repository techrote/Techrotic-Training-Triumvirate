"""Strict bounded transport-neutral messages for the game/commander boundary."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Final, cast

from techrotic_training_triumvirate.commands import parse_command_envelope
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommanderObservation,
    InterpreterResult,
    JsonObject,
    JsonValue,
    PersonaSpec,
    PlayerInterceptEnvelope,
    SchemaRecord,
    canonical_json,
    load_record,
)
from techrotic_training_triumvirate.schemas.base import (
    require_exact_keys,
    require_int,
    require_json_object,
    require_str,
    require_str_tuple,
)

RUNTIME_PROTOCOL_VERSION: Final = "ttt-runtime-v1"
RUNTIME_SCHEMA: Final = "ttt.runtime_message"
MESSAGE_KINDS: Final = (
    "health_request",
    "health",
    "reset",
    "started",
    "observation",
    "action",
    "feedback",
    "dispatch",
    "intercept",
)


class RuntimeProtocolError(ValueError):
    """Untrusted wire data failed the runtime admission boundary."""


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    """Hard ceilings applied to incoming and outgoing messages alike."""

    max_bytes: int = 65_536
    max_depth: int = 20
    max_nodes: int = 4_096
    max_items: int = 256
    max_string_bytes: int = 16_384
    max_commands: int = 8
    max_communications: int = 8
    max_events: int = 64

    def __post_init__(self) -> None:
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            raise ValueError("runtime limits must be positive integers")

    def to_dict(self) -> JsonObject:
        return cast(JsonObject, asdict(self))


DEFAULT_LIMITS: Final = RuntimeLimits()


def runtime_record[RecordT: SchemaRecord](
    value: object, *, expected_type: type[RecordT]
) -> RecordT:
    """Narrow the canonical registry loader without changing its base contract."""
    record = load_record(value, expected_type=expected_type)
    if not isinstance(record, expected_type):
        raise RuntimeProtocolError("canonical record type does not match")
    return record


def _bounded(value: object, limits: RuntimeLimits) -> None:
    remaining = limits.max_nodes

    def visit(item: object, depth: int) -> None:
        nonlocal remaining
        remaining -= 1
        if depth > limits.max_depth or remaining < 0:
            raise RuntimeProtocolError("JSON depth or node limit exceeded")
        if isinstance(item, str):
            if len(item.encode("utf-8")) > limits.max_string_bytes:
                raise RuntimeProtocolError("JSON string limit exceeded")
        elif item is None or isinstance(item, bool):
            return
        elif isinstance(item, int):
            if not -(2**63) <= item < 2**63:
                raise RuntimeProtocolError("JSON integer exceeds signed 64-bit range")
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise RuntimeProtocolError("non-finite JSON number")
        elif isinstance(item, (dict, list)):
            if len(item) > limits.max_items:
                raise RuntimeProtocolError("JSON collection limit exceeded")
            if isinstance(item, dict):
                for key, child in item.items():
                    if not isinstance(key, str):
                        raise RuntimeProtocolError("JSON keys must be strings")
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        else:
            raise RuntimeProtocolError("runtime payload must contain JSON values")

    visit(value, 0)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def bounded_json(value: object, *, limits: RuntimeLimits = DEFAULT_LIMITS) -> JsonValue:
    """Decode JSON without duplicate keys, ambiguous numbers, or unbounded trees."""
    try:
        if isinstance(value, (str, bytes)):
            raw = value.encode("utf-8") if isinstance(value, str) else value
            if len(raw) > limits.max_bytes:
                raise RuntimeProtocolError("runtime message byte limit exceeded")
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        _bounded(value, limits)
        encoded = canonical_json(value)
        if len(encoded.encode("utf-8")) > limits.max_bytes:
            raise RuntimeProtocolError("runtime message byte limit exceeded")
        # Copy nested mutable dictionaries so callers cannot retain input aliases.
        return cast(JsonValue, json.loads(encoded))
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise RuntimeProtocolError(str(exc)) from exc


def _identifier(value: object, field: str) -> str:
    result = require_str(value, field=field)
    if not result.strip() or len(result) > 128 or any(ord(c) < 32 for c in result):
        raise RuntimeProtocolError(f"{field} must be a bounded nonempty identifier")
    return result


def _natural(value: object, field: str) -> int:
    result = require_int(value, field=field)
    if result < 0:
        raise RuntimeProtocolError(f"{field} must be non-negative")
    return result


def _records[RecordT: SchemaRecord](
    value: object, record_type: type[RecordT], maximum: int
) -> tuple[RecordT, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise RuntimeProtocolError("record array exceeds its runtime bound")
    return tuple(runtime_record(item, expected_type=record_type) for item in value)


def validate_intercept_sources(
    intercept: PlayerInterceptEnvelope, sources: tuple[AuthoritativeEvent, ...]
) -> None:
    """Check exact dispatch/deception lineage before a player notification ships."""
    by_id = {event.event_id: event for event in sources}
    if len(by_id) != len(sources) or set(by_id) != set(intercept.source_event_ids):
        raise RuntimeProtocolError(
            "intercept sources must match unique source event IDs"
        )
    if len(intercept.source_event_ids) != len(by_id):
        raise RuntimeProtocolError("intercept source IDs must be unique")
    if not intercept.is_deception:
        if len(sources) != 1 or sources[0].kind != "command-dispatched":
            raise RuntimeProtocolError(
                "ordinary intercept requires exactly one dispatch"
            )
        return
    deception = by_id.get(intercept.deception_event_id or "")
    if deception is None or deception.kind != "deception-broadcast":
        raise RuntimeProtocolError(
            "deception intercept lacks its authoritative broadcast"
        )
    dispatch = by_id.get(str(deception.data.get("real_dispatch_event_id")))
    if (
        len(sources) != 2
        or dispatch is None
        or dispatch.kind != "command-dispatched"
        or deception.related_command_ids != dispatch.related_command_ids
        or deception.tick < dispatch.tick
    ):
        raise RuntimeProtocolError(
            "deception intercept lacks its real dispatch linkage"
        )


def _identity(payload: JsonObject) -> None:
    policy = require_json_object(payload["policy"], field="policy")
    require_exact_keys(policy, required={"policy_id", "adapter_id", "revision"})
    for name, value in policy.items():
        _identifier(value, name)
    artifact = payload["model_artifact"]
    if artifact is not None:
        artifact = require_json_object(artifact, field="model_artifact")
        require_exact_keys(
            artifact,
            required={"model_key", "manifest_sha256", "base_model_identity"},
        )
        _identifier(artifact["model_key"], "model_key")
        digest = require_str(artifact["manifest_sha256"], field="manifest_sha256")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise RuntimeProtocolError("manifest_sha256 must be a SHA-256 digest")
        require_json_object(
            artifact["base_model_identity"], field="base_model_identity"
        )


def _validate_payload(kind: str, payload: JsonObject, limits: RuntimeLimits) -> None:
    fields = {
        "health_request": {"runtime_protocol_versions", "command_protocol_versions"},
        "health": {
            "status",
            "implementation_version",
            "runtime_protocol_versions",
            "command_protocol_versions",
            "capabilities",
            "limits",
            "policy",
            "model_artifact",
        },
        "reset": {"seed", "persona"},
        "started": {"policy", "model_artifact"},
        "observation": {
            "observation_generation",
            "observation",
            "previous_results",
            "recent_events",
        },
        "action": {"action"},
        "feedback": {"observation_generation", "results", "events"},
        "dispatch": {"event"},
        "intercept": {"intercept"},
    }
    require_exact_keys(payload, required=fields[kind], where=f"{kind} payload")
    if kind in {"health_request", "health"}:
        for key in ("runtime_protocol_versions", "command_protocol_versions"):
            versions = require_str_tuple(payload[key], field=key)
            if not versions or len(set(versions)) != len(versions):
                raise RuntimeProtocolError(
                    "supported version arrays must be nonempty/unique"
                )
        if kind == "health":
            if payload["status"] != "ready":
                raise RuntimeProtocolError("unknown runtime health status")
            _identifier(payload["implementation_version"], "implementation_version")
            require_str_tuple(payload["capabilities"], field="capabilities")
            reported = require_json_object(payload["limits"], field="limits")
            require_exact_keys(reported, required=set(limits.to_dict()))
            for key, value in reported.items():
                if _natural(value, key) == 0:
                    raise RuntimeProtocolError("reported limits must be positive")
            _identity(payload)
    elif kind == "reset":
        _natural(payload["seed"], "seed")
        runtime_record(payload["persona"], expected_type=PersonaSpec)
    elif kind == "started":
        _identity(payload)
    elif kind == "observation":
        _natural(payload["observation_generation"], "observation_generation")
        observation = runtime_record(
            payload["observation"], expected_type=CommanderObservation
        )
        _natural(observation.turn_id, "turn_id")
        _records(payload["previous_results"], InterpreterResult, limits.max_commands)
        _records(payload["recent_events"], AuthoritativeEvent, limits.max_events)
    elif kind == "action":
        action = runtime_record(payload["action"], expected_type=AssistantAction)
        if len(action.commands) > limits.max_commands:
            raise RuntimeProtocolError("too many commands in one action")
        if len(action.communications) > limits.max_communications:
            raise RuntimeProtocolError("too many communications in one action")
        ids = [command.command_id for command in action.commands]
        if len(set(ids)) != len(ids):
            raise RuntimeProtocolError("command IDs must be unique within an action")
        for command in action.commands:
            _identifier(command.command_id, "command_id")
            parse_command_envelope(command)
        for communication in action.communications:
            _identifier(communication.communication_id, "communication_id")
    elif kind == "feedback":
        _natural(payload["observation_generation"], "observation_generation")
        _records(payload["results"], InterpreterResult, limits.max_commands)
        _records(payload["events"], AuthoritativeEvent, limits.max_events)
    elif kind == "dispatch":
        event = runtime_record(payload["event"], expected_type=AuthoritativeEvent)
        if event.kind not in {"command-dispatched", "deception-broadcast"}:
            raise RuntimeProtocolError(
                "dispatch notification requires dispatch/deception"
            )
    elif kind == "intercept":
        intercept = runtime_record(
            payload["intercept"], expected_type=PlayerInterceptEnvelope
        )
        expected_count = 2 if intercept.is_deception else 1
        if (
            len(intercept.source_event_ids) != expected_count
            or len(set(intercept.source_event_ids)) != expected_count
            or any(not event_id.strip() for event_id in intercept.source_event_ids)
            or (
                intercept.is_deception
                and intercept.deception_event_id not in intercept.source_event_ids
            )
        ):
            raise RuntimeProtocolError("intercept source event IDs are inconsistent")


@dataclass(frozen=True, slots=True)
class RuntimeMessage:
    """A versioned wire envelope; endpoints revalidate even in-process objects."""

    kind: str
    session_id: str
    request_id: str
    sequence: int
    payload: JsonObject

    def to_dict(self) -> JsonObject:
        return {
            "schema": RUNTIME_SCHEMA,
            "schema_version": 1,
            "protocol_version": RUNTIME_PROTOCOL_VERSION,
            "kind": self.kind,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "sequence": self.sequence,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


def parse_runtime_message(
    value: object, *, limits: RuntimeLimits = DEFAULT_LIMITS
) -> RuntimeMessage:
    try:
        if isinstance(value, RuntimeMessage):
            value = value.to_dict()
        raw = require_json_object(bounded_json(value, limits=limits), field="message")
        require_exact_keys(
            raw,
            required={
                "schema",
                "schema_version",
                "protocol_version",
                "kind",
                "session_id",
                "request_id",
                "sequence",
                "payload",
            },
        )
        if raw["schema"] != RUNTIME_SCHEMA or type(raw["schema_version"]) is not int:
            raise RuntimeProtocolError("unsupported runtime schema/version")
        if (
            raw["schema_version"] != 1
            or raw["protocol_version"] != RUNTIME_PROTOCOL_VERSION
        ):
            raise RuntimeProtocolError("unsupported runtime schema/protocol version")
        kind = require_str(raw["kind"], field="kind")
        if kind not in MESSAGE_KINDS:
            raise RuntimeProtocolError("unsupported runtime message kind")
        session_id = _identifier(raw["session_id"], "session_id")
        request_id = _identifier(raw["request_id"], "request_id")
        sequence = _natural(raw["sequence"], "sequence")
        payload = require_json_object(raw["payload"], field="payload")
        _validate_payload(kind, payload, limits)
        return RuntimeMessage(kind, session_id, request_id, sequence, payload)
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeProtocolError(str(exc)) from exc


def runtime_message(
    kind: str,
    *,
    session_id: str,
    sequence: int,
    payload: JsonObject,
    request_id: str | None = None,
    limits: RuntimeLimits = DEFAULT_LIMITS,
) -> RuntimeMessage:
    """Construct only messages accepted by the same strict wire parser."""
    return parse_runtime_message(
        RuntimeMessage(
            kind, session_id, request_id or f"{kind}-{sequence}", sequence, payload
        ),
        limits=limits,
    )
