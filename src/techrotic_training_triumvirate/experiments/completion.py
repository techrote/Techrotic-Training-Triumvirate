"""Durable stage completion markers with independently verified artifact hashes."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    canonical_json,
    content_hash,
)
from techrotic_training_triumvirate.training.export import sha256_file

from .model import EvidenceClass


class CompletionMarkerError(ValueError):
    """A stage completion marker or its artifact inventory is unsafe."""


def _artifact_path(root: Path, name: str) -> Path:
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
        raise CompletionMarkerError("artifact path escapes the stage directory")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise CompletionMarkerError(f"artifact is missing: {name}")
    return path


def _fsync_directory(path: Path) -> None:
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


def _inventory(root: Path, names: tuple[str, ...]) -> JsonObject:
    if not names or len(set(names)) != len(names):
        raise CompletionMarkerError("artifact inventory must be non-empty and unique")
    inventory: JsonObject = {}
    for name in sorted(names):
        if name == "COMPLETE.json":
            raise CompletionMarkerError("completion marker cannot inventory itself")
        path = _artifact_path(root, name)
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
        inventory[name] = sha256_file(path)
    return inventory


def write_completion_marker(
    directory: str | Path,
    *,
    stage_id: str,
    artifact_names: tuple[str, ...],
    evidence_class: EvidenceClass,
) -> JsonObject:
    """Fsync artifacts then atomically publish their final immutable inventory."""

    if not stage_id:
        raise CompletionMarkerError("stage_id must be non-empty")
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    inventory = _inventory(root, artifact_names)
    record: JsonObject = {
        "schema": "ttt.stage_completion",
        "schema_version": 1,
        "complete": True,
        "stage_id": stage_id,
        "evidence_class": evidence_class.value,
        "artifacts": inventory,
        "inventory_sha256": content_hash(inventory),
    }
    marker = root / "COMPLETE.json"
    if marker.exists():
        existing = verify_completion_marker(
            root,
            stage_id=stage_id,
            evidence_class=evidence_class,
        )
        if existing != record:
            raise CompletionMarkerError("existing completion marker differs")
        return existing

    temporary = root / f".COMPLETE.{os.getpid()}.tmp"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, marker)
        _fsync_directory(root)
    finally:
        temporary.unlink(missing_ok=True)
    return record


def verify_completion_marker(
    directory: str | Path,
    *,
    stage_id: str,
    evidence_class: EvidenceClass,
) -> JsonObject:
    """Verify marker identity and every artifact byte independently."""

    root = Path(directory).resolve()
    marker = root / "COMPLETE.json"
    try:
        if marker.stat().st_size > 4_194_304:
            raise CompletionMarkerError("completion marker exceeds four MiB")
        value: object = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompletionMarkerError("completion marker is missing or invalid") from exc
    if not isinstance(value, dict):
        raise CompletionMarkerError("completion marker must be a JSON object")
    required = {
        "schema",
        "schema_version",
        "complete",
        "stage_id",
        "evidence_class",
        "artifacts",
        "inventory_sha256",
    }
    if set(value) != required:
        raise CompletionMarkerError("completion marker fields differ from schema")
    if (
        value["schema"] != "ttt.stage_completion"
        or value["schema_version"] != 1
        or value["complete"] is not True
        or value["stage_id"] != stage_id
        or value["evidence_class"] != evidence_class.value
    ):
        raise CompletionMarkerError("completion marker identity differs")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise CompletionMarkerError("completion artifact inventory is invalid")
    verified: JsonObject = {}
    for raw_name, raw_digest in sorted(artifacts.items()):
        if not isinstance(raw_name, str) or not isinstance(raw_digest, str):
            raise CompletionMarkerError("completion artifact entry is invalid")
        if (
            len(raw_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in raw_digest)
        ):
            raise CompletionMarkerError("completion artifact digest is invalid")
        if sha256_file(_artifact_path(root, raw_name)) != raw_digest:
            raise CompletionMarkerError(f"artifact hash differs: {raw_name}")
        verified[raw_name] = raw_digest
    if content_hash(verified) != value["inventory_sha256"]:
        raise CompletionMarkerError("completion inventory hash differs")
    return {
        "schema": "ttt.stage_completion",
        "schema_version": 1,
        "complete": True,
        "stage_id": stage_id,
        "evidence_class": evidence_class.value,
        "artifacts": verified,
        "inventory_sha256": value["inventory_sha256"],
    }
