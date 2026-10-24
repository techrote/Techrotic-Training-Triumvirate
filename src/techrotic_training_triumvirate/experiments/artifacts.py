"""Atomic completion markers and independent artifact verification."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    canonical_json,
    content_hash,
)
from techrotic_training_triumvirate.schemas.base import require_json_object
from techrotic_training_triumvirate.training.export import sha256_file

from .model import EvidenceClass, OrchestrationError


class ArtifactVerificationError(OrchestrationError):
    """A completion marker or its artifact inventory cannot be trusted."""


def _safe_artifact(root: Path, name: str) -> Path:
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if (
        not name
        or "\\" in name
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise ArtifactVerificationError("artifact path escapes the attempt directory")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ArtifactVerificationError(
            "artifact is missing from the attempt directory"
        )
    return path


def _sync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _validate_stage_id(stage_id: str) -> None:
    if (
        len(stage_id) != 64
        or any(character not in "0123456789abcdef" for character in stage_id)
    ):
        raise ArtifactVerificationError("stage identity must be a lowercase SHA-256")


def write_completion_marker(
    directory: str | Path,
    *,
    stage_id: str,
    artifact_names: tuple[str, ...],
    evidence_class: EvidenceClass,
) -> Path:
    """Hash closed artifacts, fsync, then atomically publish the final marker."""

    _validate_stage_id(stage_id)
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not artifact_names or len(set(artifact_names)) != len(artifact_names):
        raise ArtifactVerificationError(
            "completion inventory must be nonempty and unique"
        )
    inventory: JsonObject = {}
    for name in sorted(artifact_names):
        if name == "COMPLETE.json":
            raise ArtifactVerificationError("completion marker cannot inventory itself")
        path = _safe_artifact(root, name)
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
        inventory[name] = sha256_file(path)
    payload: JsonObject = {
        "schema": "ttt.experiment_completion",
        "schema_version": 1,
        "complete": True,
        "stage_id": stage_id,
        "evidence_class": evidence_class.value,
        "artifacts": inventory,
        "inventory_hash": content_hash(inventory),
    }
    temporary = root / f".COMPLETE.{os.getpid()}.tmp"
    marker = root / "COMPLETE.json"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, marker)
        _sync_directory(root)
    finally:
        temporary.unlink(missing_ok=True)
    return marker


def verify_completion_marker(
    directory: str | Path,
    *,
    expected_stage_id: str,
    expected_evidence_class: EvidenceClass | None = None,
) -> dict[str, str]:
    """Independently verify the marker and every artifact byte."""

    _validate_stage_id(expected_stage_id)
    root = Path(directory).resolve()
    marker = root / "COMPLETE.json"
    try:
        if marker.stat().st_size > 4_194_304:
            raise ArtifactVerificationError("completion marker exceeds four MiB")
        value: object = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactVerificationError(
            "completion marker is missing or invalid"
        ) from exc
    payload = require_json_object(value, field="completion marker")
    required = {
        "schema",
        "schema_version",
        "complete",
        "stage_id",
        "evidence_class",
        "artifacts",
        "inventory_hash",
    }
    if set(payload) != required:
        raise ArtifactVerificationError("completion marker fields differ from schema")
    if (
        payload["schema"] != "ttt.experiment_completion"
        or payload["schema_version"] != 1
        or payload["complete"] is not True
        or payload["stage_id"] != expected_stage_id
    ):
        raise ArtifactVerificationError("completion marker identity differs")
    try:
        evidence_class = EvidenceClass(str(payload["evidence_class"]))
    except ValueError as exc:
        raise ArtifactVerificationError("completion evidence class is invalid") from exc
    if (
        expected_evidence_class is not None
        and evidence_class != expected_evidence_class
    ):
        raise ArtifactVerificationError("completion evidence class differs")
    artifacts = require_json_object(payload["artifacts"], field="artifacts")
    if not artifacts:
        raise ArtifactVerificationError("completion inventory is empty")
    verified: dict[str, str] = {}
    for name, raw_digest in sorted(artifacts.items()):
        if not isinstance(raw_digest, str):
            raise ArtifactVerificationError("artifact digest must be a string")
        digest = raw_digest
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ArtifactVerificationError("artifact digest is not SHA-256")
        if sha256_file(_safe_artifact(root, name)) != digest:
            raise ArtifactVerificationError(f"artifact hash differs: {name}")
        verified[name] = digest
    if content_hash(verified) != payload["inventory_hash"]:
        raise ArtifactVerificationError("completion inventory hash differs")
    return verified


def inventory_hash(inventory: Mapping[str, str]) -> str:
    """Hash an already-verified portable inventory."""

    return content_hash(dict(sorted(inventory.items())))
