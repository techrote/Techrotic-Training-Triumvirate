"""Semantic and versioned data structures for player intercept encoding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    JsonObject,
    JsonValue,
    SchemaValidationError,
)

INTERCEPT_CODEC_VERSION: Final[str] = "ttt-intercept-v1"
INTERCEPTABLE_FIELDS: Final[tuple[str, ...]] = (
    "op",
    "unit_id",
    "unit_ids",
    "target_id",
    "approach",
    "trigger",
    "urgency",
    "channel",
)


@dataclass(frozen=True, slots=True)
class DoctrineLexicon:
    doctrine_id: str
    version: int
    aliases: dict[str, str]

    def __post_init__(self) -> None:
        if not self.doctrine_id.strip():
            raise ValueError("doctrine_id must not be empty")
        if self.version < 1:
            raise ValueError("doctrine version must be positive")
        if any(
            not key.strip() or not value.strip()
            for key, value in self.aliases.items()
        ):
            raise ValueError("doctrine aliases must use non-empty strings")

    def alias(self, field: str, value: str) -> str:
        return self.aliases.get(f"{field}:{value}", value)


@dataclass(frozen=True, slots=True)
class SemanticIntercept:
    source_event_id: str
    tick: int
    fields: JsonObject

    @classmethod
    def from_dispatch_event(cls, event: AuthoritativeEvent) -> SemanticIntercept:
        if event.kind != "command-dispatched":
            raise SchemaValidationError(
                "ordinary semantic intercepts require command-dispatched events"
            )
        fields: JsonObject = {}
        for field in INTERCEPTABLE_FIELDS:
            if field in event.data:
                fields[field] = event.data[field]
        if "op" not in fields:
            raise SchemaValidationError("dispatch event must expose an op field")
        return cls(source_event_id=event.event_id, tick=event.tick, fields=fields)


@dataclass(frozen=True, slots=True)
class DeceptionBroadcast:
    deception_event_id: str
    real_dispatch_event_id: str
    tick: int
    false_semantics: JsonObject

    def __post_init__(self) -> None:
        if not self.deception_event_id.strip():
            raise ValueError("deception_event_id must not be empty")
        if not self.real_dispatch_event_id.strip():
            raise ValueError("real_dispatch_event_id must not be empty")
        unknown = set(self.false_semantics) - set(INTERCEPTABLE_FIELDS)
        if unknown:
            raise ValueError(
                f"false semantics contain unsupported fields: {sorted(unknown)}"
            )
        if "op" not in self.false_semantics:
            raise ValueError("false semantics require op")


def deception_event(
    real_dispatch: AuthoritativeEvent,
    *,
    deception_event_id: str,
    false_semantics: JsonObject,
    tick: int | None = None,
) -> AuthoritativeEvent:
    """Create an authoritative event representing a deliberate false broadcast."""
    if real_dispatch.kind != "command-dispatched":
        raise ValueError("deception must reference a command-dispatched event")
    broadcast = DeceptionBroadcast(
        deception_event_id=deception_event_id,
        real_dispatch_event_id=real_dispatch.event_id,
        tick=real_dispatch.tick if tick is None else tick,
        false_semantics=false_semantics,
    )
    data: JsonObject = {
        "real_dispatch_event_id": broadcast.real_dispatch_event_id,
        "false_semantics": broadcast.false_semantics,
    }
    return AuthoritativeEvent(
        event_id=broadcast.deception_event_id,
        kind="deception-broadcast",
        tick=broadcast.tick,
        related_command_ids=real_dispatch.related_command_ids,
        data=data,
    )


def false_semantics_from_event(event: AuthoritativeEvent) -> JsonObject:
    if event.kind != "deception-broadcast":
        raise SchemaValidationError("event is not an explicit deception broadcast")
    raw = event.data.get("false_semantics")
    if not isinstance(raw, dict):
        raise SchemaValidationError("deception event lacks false_semantics object")
    result: JsonObject = {}
    for key, value in raw.items():
        if key not in INTERCEPTABLE_FIELDS:
            raise SchemaValidationError(f"unsupported deception field: {key}")
        result[key] = value
    if "op" not in result:
        raise SchemaValidationError("deception false semantics require op")
    return result


def string_value(value: JsonValue) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ",".join(string_value(item) for item in value)
    if value is None:
        return "null"
    if isinstance(value, dict):
        raise ValueError("nested objects are not renderable intercept fields")
    return str(value)
