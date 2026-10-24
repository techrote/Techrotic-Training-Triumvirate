"""Deterministic, replaceable commander/session rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from techrotic_training_triumvirate.schemas import (
    CommanderObservation,
    InterpreterResult,
    JsonObject,
    JsonValue,
    canonical_json,
    content_hash,
)

SESSION_RENDERER_VERSION = "ttt-session-renderer-v1"


def _escape_pointer(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _unescape_pointer(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _pointer(parts: tuple[str, ...]) -> str:
    if not parts:
        return ""
    return "/" + "/".join(_escape_pointer(part) for part in parts)


def _split_pointer(pointer: str) -> tuple[str, ...]:
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must be empty or begin with '/'")
    return tuple(_unescape_pointer(part) for part in pointer[1:].split("/"))


def _copy_json(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {key: _copy_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class SemanticDelta:
    """Deterministic semantic delta over commander-visible JSON only."""

    base_hash: str
    target_hash: str
    set_values: JsonObject
    removed_paths: tuple[str, ...]

    def to_dict(self) -> JsonObject:
        return {
            "base_hash": self.base_hash,
            "target_hash": self.target_hash,
            "set": self.set_values,
            "remove": list(self.removed_paths),
        }


def _diff(
    previous: JsonValue,
    current: JsonValue,
    *,
    parts: tuple[str, ...],
    set_values: dict[str, JsonValue],
    removed_paths: list[str],
) -> None:
    if previous == current:
        return
    if isinstance(previous, dict) and isinstance(current, dict):
        previous_keys = set(previous)
        current_keys = set(current)
        for key in sorted(previous_keys - current_keys):
            removed_paths.append(_pointer((*parts, key)))
        for key in sorted(current_keys):
            if key not in previous:
                set_values[_pointer((*parts, key))] = _copy_json(current[key])
                continue
            _diff(
                previous[key],
                current[key],
                parts=(*parts, key),
                set_values=set_values,
                removed_paths=removed_paths,
            )
        return
    set_values[_pointer(parts)] = _copy_json(current)


def compute_delta(
    previous: CommanderObservation,
    current: CommanderObservation,
) -> SemanticDelta:
    """Compute a stable JSON-pointer delta between admitted observations."""
    previous_payload = previous.to_payload()
    current_payload = current.to_payload()
    set_values: dict[str, JsonValue] = {}
    removed_paths: list[str] = []
    _diff(
        previous_payload,
        current_payload,
        parts=(),
        set_values=set_values,
        removed_paths=removed_paths,
    )
    return SemanticDelta(
        base_hash=previous.content_hash(),
        target_hash=current.content_hash(),
        set_values=dict(sorted(set_values.items())),
        removed_paths=tuple(sorted(removed_paths)),
    )


def _parent_for_path(
    root: JsonObject,
    parts: tuple[str, ...],
) -> tuple[JsonObject, str]:
    if not parts:
        raise ValueError("root path has no parent")
    current = root
    for token in parts[:-1]:
        value = current.get(token)
        if not isinstance(value, dict):
            raise ValueError(f"delta path parent is not an object: {_pointer(parts)}")
        current = value
    return current, parts[-1]


def apply_delta(
    previous: CommanderObservation,
    delta: SemanticDelta,
) -> JsonObject:
    """Apply a semantic delta and return the reconstructed observation payload."""
    if previous.content_hash() != delta.base_hash:
        raise ValueError("delta base hash does not match previous observation")
    root_value = _copy_json(previous.to_payload())
    if not isinstance(root_value, dict):
        raise AssertionError("commander observation payload must be an object")
    root = root_value
    for path in delta.removed_paths:
        parts = _split_pointer(path)
        if not parts:
            raise ValueError("cannot remove the root observation payload")
        parent, key = _parent_for_path(root, parts)
        if key not in parent:
            raise ValueError(f"delta removes missing path: {path}")
        del parent[key]
    for path, value in delta.set_values.items():
        parts = _split_pointer(path)
        if not parts:
            if not isinstance(value, dict):
                raise ValueError("root replacement must be an object")
            root = _copy_json(value)
            if not isinstance(root, dict):
                raise AssertionError("root replacement must stay an object")
            continue
        parent, key = _parent_for_path(root, parts)
        parent[key] = _copy_json(value)
    if content_hash(
        {
            "schema": CommanderObservation.SCHEMA_NAME,
            "schema_version": CommanderObservation.SCHEMA_VERSION,
            "payload": root,
        }
    ) != delta.target_hash:
        raise ValueError("reconstructed observation hash does not match delta target")
    return root


class SessionRenderer(Protocol):
    """Replaceable presentation layer; no terminal representation is canonical."""

    version: str

    def structured_observation(self, observation: CommanderObservation) -> JsonObject:
        """Return commander-visible structured content."""

    def compact_observation(self, observation: CommanderObservation) -> str:
        """Return deterministic compact text."""

    def compact_result(self, result: InterpreterResult) -> str:
        """Render authoritative interpreter acknowledgement/error."""

    def compact_delta(self, delta: SemanticDelta) -> str:
        """Render deterministic semantic delta text."""


@dataclass(frozen=True, slots=True)
class DeterministicRenderer:
    version: str = SESSION_RENDERER_VERSION

    def structured_observation(self, observation: CommanderObservation) -> JsonObject:
        return observation.to_payload()

    def compact_observation(self, observation: CommanderObservation) -> str:
        entities = ",".join(observation.visible_entities) or "-"
        objectives = ",".join(observation.objective_ids) or "-"
        events = ",".join(observation.event_ids) or "-"
        return " | ".join(
            (
                f"TURN {observation.turn_id}",
                f"STATE {observation.world_state_id}",
                f"ENTITIES {entities}",
                f"OBJECTIVES {objectives}",
                f"EVENTS {events}",
                f"FACTS {canonical_json(observation.facts)}",
            )
        )

    def compact_result(self, result: InterpreterResult) -> str:
        kind = "ACK" if result.accepted else "ERR"
        return (
            f"{kind} {result.command_id} {result.code} "
            f"{canonical_json(result.detail)}"
        )

    def compact_delta(self, delta: SemanticDelta) -> str:
        return (
            f"DELTA {delta.base_hash[:12]}->{delta.target_hash[:12]} "
            f"SET {canonical_json(delta.set_values)} "
            f"REMOVE {canonical_json(list(delta.removed_paths))}"
        )
