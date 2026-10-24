"""Versioned record envelope, strict loading, canonical JSON, and hashing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
import hashlib
import json
import math
from typing import ClassVar, Self, TypeAlias, TypeVar, cast


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = (
    JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
)
JsonObject: TypeAlias = dict[str, JsonValue]


class SchemaError(ValueError):
    """Base error for canonical schema failures."""


class UnknownSchemaError(SchemaError):
    """Raised when an envelope names an unregistered schema."""


class UnsupportedSchemaVersionError(SchemaError):
    """Raised when a known schema uses an unsupported version."""


class SchemaValidationError(SchemaError):
    """Raised when an envelope or payload is structurally invalid."""


class SchemaRecord(ABC):
    """Base class for all durable TTT records."""

    SCHEMA_NAME: ClassVar[str]
    SCHEMA_VERSION: ClassVar[int] = 1

    @abstractmethod
    def to_payload(self) -> JsonObject:
        """Return this record's schema-specific JSON payload."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_payload(cls, payload: JsonObject) -> Self:
        """Construct and validate a record from a schema-specific payload."""
        raise NotImplementedError

    def to_dict(self) -> JsonObject:
        """Return the durable versioned envelope."""
        return {
            "schema": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "payload": self.to_payload(),
        }

    def to_json(self) -> str:
        """Return canonical JSON suitable for hashing and durable fixtures."""
        return canonical_json(self)

    def content_hash(self) -> str:
        """Return SHA-256 of the canonical durable representation."""
        return content_hash(self)


RecordT = TypeVar("RecordT", bound=SchemaRecord)
_RECORD_TYPES: dict[str, type[SchemaRecord]] = {}


def register_record(cls: type[RecordT]) -> type[RecordT]:
    """Register a durable record class by its stable schema name."""
    if not cls.SCHEMA_NAME:
        raise ValueError("schema name must not be empty")
    previous = _RECORD_TYPES.get(cls.SCHEMA_NAME)
    if previous is not None and previous is not cls:
        raise ValueError(f"duplicate schema name: {cls.SCHEMA_NAME}")
    _RECORD_TYPES[cls.SCHEMA_NAME] = cls
    return cls


def registered_record_types() -> Mapping[str, type[SchemaRecord]]:
    """Return a read-only logical view of registered schema types."""
    return dict(sorted(_RECORD_TYPES.items()))


def _normalize_json(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SchemaValidationError("non-finite floats are not canonical JSON")
        return value
    if isinstance(value, SchemaRecord):
        return value.to_dict()
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SchemaValidationError("JSON object keys must be strings")
            normalized[key] = _normalize_json(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item) for item in value]
    raise SchemaValidationError(
        f"unsupported canonical JSON value: {type(value).__name__}"
    )


def canonical_json(value: object) -> str:
    """Serialize a JSON-compatible value or record canonically."""
    normalized = _normalize_json(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def content_hash(value: object) -> str:
    """Return the SHA-256 hash of canonical JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _expect_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{where} must be a JSON object")
    for key in value:
        if not isinstance(key, str):
            raise SchemaValidationError(f"{where} keys must be strings")
    return cast(JsonObject, value)


def require_exact_keys(
    payload: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str] | None = None,
    where: str = "payload",
) -> None:
    """Require an exact known key set, permitting named optional keys."""
    optional_keys = optional or set()
    actual = set(payload)
    missing = required - actual
    unknown = actual - required - optional_keys
    if missing:
        raise SchemaValidationError(
            f"{where} missing required fields: {sorted(missing)}"
        )
    if unknown:
        raise SchemaValidationError(
            f"{where} has unknown fields: {sorted(unknown)}"
        )


def require_str(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(f"{field} must be a string")
    return value


def require_optional_str(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return require_str(value, field=field)


def require_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaValidationError(f"{field} must be an integer")
    return value


def require_bool(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(f"{field} must be a boolean")
    return value


def require_str_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{field} must be an array of strings")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(require_str(item, field=f"{field}[{index}]"))
    return tuple(result)


def require_json_object(value: object, *, field: str) -> JsonObject:
    raw = _expect_object(value, where=field)
    normalized = _normalize_json(raw)
    if not isinstance(normalized, dict):
        raise AssertionError("object normalization must produce an object")
    return normalized


def load_record(
    value: object,
    *,
    expected_type: type[RecordT] | None = None,
) -> SchemaRecord | RecordT:
    """Load a strict versioned record envelope."""
    envelope = _expect_object(value, where="record envelope")
    require_exact_keys(
        envelope,
        required={"schema", "schema_version", "payload"},
        where="record envelope",
    )
    schema_name = require_str(envelope["schema"], field="schema")
    schema_version = require_int(
        envelope["schema_version"], field="schema_version"
    )
    record_type = _RECORD_TYPES.get(schema_name)
    if record_type is None:
        raise UnknownSchemaError(f"unknown schema: {schema_name}")
    if schema_version != record_type.SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"{schema_name} version {schema_version} is unsupported; "
            f"supported version is {record_type.SCHEMA_VERSION}"
        )
    if expected_type is not None and record_type is not expected_type:
        raise SchemaValidationError(
            f"expected {expected_type.SCHEMA_NAME}, got {schema_name}"
        )
    payload = require_json_object(envelope["payload"], field="payload")
    record = record_type.from_payload(payload)
    if expected_type is not None:
        return cast(RecordT, record)
    return record


def loads_record(
    text: str,
    *,
    expected_type: type[RecordT] | None = None,
) -> SchemaRecord | RecordT:
    """Parse canonical/non-canonical JSON into a strict versioned record."""
    try:
        value: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"invalid JSON: {exc.msg}") from exc
    return load_record(value, expected_type=expected_type)
