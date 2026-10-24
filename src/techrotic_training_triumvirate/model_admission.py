"""Immutable initial model-cast admission helpers for TTT-011."""

from __future__ import annotations

import hashlib
import json
import re
from importlib.resources import files
from typing import Any, Mapping, cast

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MUTABLE_REFS = {"head", "latest", "main", "master"}


class ModelAdmissionError(ValueError):
    """Raised when the committed model-cast admission is inconsistent."""


def load_model_cast_v1() -> dict[str, Any]:
    """Load the committed TTT-011 model-cast admission."""
    raw = (files("techrotic_training_triumvirate") / "model_cast_v1.json").read_text(
        encoding="utf-8"
    )
    parsed: object = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ModelAdmissionError("model-cast document must be a JSON object")
    return cast(dict[str, Any], parsed)


def model_cast_content_hash(data: Mapping[str, Any] | None = None) -> str:
    """Return the canonical SHA-256 of the admission document."""
    payload = load_model_cast_v1() if data is None else dict(data)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _require_str(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelAdmissionError(f"{path} must be a non-empty string")
    return value


def _validate_sha256(value: object, path: str) -> None:
    text = _require_str(value, path).lower()
    if _SHA256.fullmatch(text) is None:
        raise ModelAdmissionError(f"{path} must be a 64-character SHA-256")


def _validate_immutable_identity(record: Mapping[str, Any], path: str) -> None:
    sha = record.get("artifact_sha256")
    revision = record.get("revision")
    commit = record.get("artifact_commit")

    if sha is not None:
        _validate_sha256(sha, f"{path}.artifact_sha256")
        return

    ref = revision if revision is not None else commit
    text = _require_str(ref, f"{path}.revision").lower()
    if text in _MUTABLE_REFS:
        raise ModelAdmissionError(
            f"{path} must not use mutable ref {text!r} as its sole identity"
        )
    if len(text) < 7 or re.fullmatch(r"[0-9a-f]+", text) is None:
        raise ModelAdmissionError(
            f"{path} revision must be an immutable hexadecimal commit identifier"
        )


def validate_model_cast_v1(data: Mapping[str, Any] | None = None) -> None:
    """Validate the TTT-011 cast and fail closed on mutable identities."""
    cast_data = load_model_cast_v1() if data is None else data

    if cast_data.get("schema_version") != 1:
        raise ModelAdmissionError("unsupported model-cast schema version")
    if cast_data.get("decision_status") != "SELECTED":
        raise ModelAdmissionError("model cast is not selected")

    roles = cast_data.get("roles")
    if not isinstance(roles, Mapping):
        raise ModelAdmissionError("roles must be an object")
    primary = _require_str(
        roles.get("primary_compact_student"),
        "roles.primary_compact_student",
    )

    models = cast_data.get("models")
    if not isinstance(models, Mapping) or not models:
        raise ModelAdmissionError("models must be a non-empty object")
    if primary not in models:
        raise ModelAdmissionError("primary student must resolve to an admitted model")

    selected_primary_count = 0
    for model_key, raw_record in models.items():
        key = _require_str(model_key, "models key")
        if not isinstance(raw_record, Mapping):
            raise ModelAdmissionError(f"models.{key} must be an object")
        if raw_record.get("status") != "selected":
            raise ModelAdmissionError(f"models.{key} is not selected")

        model_roles = raw_record.get("roles")
        if not isinstance(model_roles, list) or not model_roles:
            raise ModelAdmissionError(f"models.{key}.roles must be a non-empty list")
        if "primary_compact_student" in model_roles:
            selected_primary_count += 1

        license_record = raw_record.get("license")
        if not isinstance(license_record, Mapping):
            raise ModelAdmissionError(f"models.{key}.license must be an object")
        _require_str(license_record.get("id"), f"models.{key}.license.id")
        _require_str(
            license_record.get("generated_output_training_use"),
            f"models.{key}.license.generated_output_training_use",
        )

        native = raw_record.get("native")
        inference = raw_record.get("inference")
        if not isinstance(native, Mapping) or not isinstance(inference, Mapping):
            raise ModelAdmissionError(
                f"models.{key} must define native and inference identities"
            )
        _validate_immutable_identity(native, f"models.{key}.native")
        _validate_immutable_identity(inference, f"models.{key}.inference")

        evidence = raw_record.get("measured_characterization")
        if not isinstance(evidence, Mapping):
            raise ModelAdmissionError(
                f"models.{key}.measured_characterization must be an object"
            )
        items = evidence.get("evidence")
        if not isinstance(items, list) or not items:
            raise ModelAdmissionError(
                f"models.{key}.measured_characterization.evidence must be non-empty"
            )

    if selected_primary_count != 1:
        raise ModelAdmissionError("exactly one selected primary compact student is required")

    budget = cast_data.get("training_budget")
    targets = cast_data.get("runtime_targets")
    if not isinstance(budget, Mapping) or not isinstance(targets, Mapping):
        raise ModelAdmissionError("training_budget and runtime_targets are required")


def selected_model_keys() -> tuple[str, ...]:
    """Return selected model keys in committed order."""
    data = load_model_cast_v1()
    validate_model_cast_v1(data)
    models = cast(dict[str, Any], data["models"])
    return tuple(models)
