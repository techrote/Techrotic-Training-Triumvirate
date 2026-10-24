"""Deterministic visibility, redaction, alias, noise, and delay policies."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random

from techrotic_training_triumvirate.schemas import JsonObject, JsonValue, canonical_json

from .model import DoctrineLexicon, INTERCEPTABLE_FIELDS, string_value


class InterceptVisibilityError(ValueError):
    """Raised when a candidate intercept would disclose forbidden material."""


@dataclass(frozen=True, slots=True)
class InterceptPolicy:
    policy_id: str
    version: int = 1
    reveal_fields: tuple[str, ...] = (
        "op",
        "unit_id",
        "unit_ids",
        "target_id",
        "approach",
        "trigger",
        "urgency",
    )
    redact_fields: tuple[str, ...] = ()
    alias_fields: tuple[str, ...] = (
        "unit_id",
        "unit_ids",
        "target_id",
        "approach",
        "trigger",
    )
    drop_probability: float = 0.0
    corruption_probability: float = 0.0
    delay_ticks: int = 0
    seed: int = 0
    forbidden_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty")
        if self.version < 1:
            raise ValueError("policy version must be positive")
        for name, probability in (
            ("drop_probability", self.drop_probability),
            ("corruption_probability", self.corruption_probability),
        ):
            if not 0.0 <= probability <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.delay_ticks < 0:
            raise ValueError("delay_ticks must be non-negative")
        allowed = set(INTERCEPTABLE_FIELDS)
        for collection_name, fields in (
            ("reveal_fields", self.reveal_fields),
            ("redact_fields", self.redact_fields),
            ("alias_fields", self.alias_fields),
        ):
            unknown = set(fields) - allowed
            if unknown:
                raise ValueError(
                    f"{collection_name} contains unsupported fields: {sorted(unknown)}"
                )

    def rng_for(self, *, event_id: str, stage: str) -> random.Random:
        material = canonical_json(
            {
                "event_id": event_id,
                "policy_id": self.policy_id,
                "policy_version": self.version,
                "seed": self.seed,
                "stage": stage,
            }
        )
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))


def _alias_scalar(
    field: str,
    value: JsonValue,
    doctrine: DoctrineLexicon,
) -> JsonValue:
    if isinstance(value, str):
        return doctrine.alias(field, value)
    if isinstance(value, list):
        return [
            doctrine.alias(field, item) if isinstance(item, str) else item
            for item in value
        ]
    return value


def apply_semantic_policy(
    fields: JsonObject,
    *,
    event_id: str,
    doctrine: DoctrineLexicon,
    policy: InterceptPolicy,
) -> JsonObject:
    """Return deterministic visible semantic fields from authoritative semantics."""
    visible: JsonObject = {}
    drop_rng = policy.rng_for(event_id=event_id, stage="drop")

    for field in policy.reveal_fields:
        if field not in fields:
            continue
        if field != "op" and policy.drop_probability:
            if drop_rng.random() < policy.drop_probability:
                continue
        value: JsonValue = fields[field]
        if field in policy.redact_fields:
            value = "[REDACTED]"
        elif field in policy.alias_fields:
            value = _alias_scalar(field, value, doctrine)
        visible[field] = value

    if "op" not in visible and "op" in fields:
        visible["op"] = fields["op"]

    rendered_surface = canonical_json(visible)
    for forbidden in policy.forbidden_values:
        if forbidden and forbidden in rendered_surface:
            raise InterceptVisibilityError(
                "intercept would disclose a forbidden visibility value"
            )
    return visible


def render_semantics(
    fields: JsonObject,
    *,
    event_id: str,
    policy: InterceptPolicy,
) -> str:
    """Render a deterministic compact radio-like representation."""
    ordered = [
        f"{field.upper()}={string_value(fields[field])}"
        for field in INTERCEPTABLE_FIELDS
        if field in fields
    ]
    rendered = " | ".join(ordered)

    if not rendered or policy.corruption_probability <= 0.0:
        return rendered

    rng = policy.rng_for(event_id=event_id, stage="corruption")
    chars = list(rendered)
    for index, char in enumerate(chars):
        if char.isalnum() and rng.random() < policy.corruption_probability:
            chars[index] = "?"
    return "".join(chars)
