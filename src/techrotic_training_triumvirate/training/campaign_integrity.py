"""Strict identity readback for completed training outputs before campaign reuse.

This module is separate from the campaign source used for the recorded pilot.
Import it into orchestration only after that execution has finished.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    RunManifest,
    content_hash,
    load_record,
)
from techrotic_training_triumvirate.schemas.base import require_json_object

from .export import sha256_file
from .model import DatasetIdentity, ModelBinding, TrainingConfig


class CampaignIntegrityError(ValueError):
    """A candidate's persisted evidence differs from the requested experiment."""


def _read(path: Path) -> JsonObject:
    if path.stat().st_size > 4_194_304:
        raise CampaignIntegrityError("training metadata exceeds four MiB")
    return require_json_object(
        json.loads(path.read_text(encoding="utf-8")), field=path.name
    )


def _artifact(root: Path, name: str) -> Path:
    posix, windows = PurePosixPath(name), PureWindowsPath(name)
    if (
        not name
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise CampaignIntegrityError("training artifact path escapes the run directory")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise CampaignIntegrityError(
            "training artifact is not contained in the run directory"
        )
    return path


def expected_training_identity(
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    source_revision: str | None = None,
) -> JsonObject:
    """Build source-bound v2 identity, or historical v1 for completed readback."""
    payload: JsonObject = {
        "model_binding": binding.to_object(),
        "training_config": config.to_object(),
        "dataset_identity": dataset.to_object(),
        "backend": config.backend,
    }
    version = 1
    if source_revision is not None:
        if len(source_revision) != 40 or any(
            c not in "0123456789abcdef" for c in source_revision
        ):
            raise CampaignIntegrityError(
                "source revision must be a full immutable Git SHA"
            )
        payload["source_revision"] = source_revision
        version = 2
    return {
        "schema_version": version,
        "training_identity": content_hash(payload),
        **payload,
    }


def verify_checkpoint_identity(
    directory: str | Path,
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    source_revision: str,
) -> str:
    """Require v2 source identity before any interrupted checkpoint can resume."""
    try:
        root = Path(directory).resolve()
        saved = _read(_artifact(root, "training-identity.json"))
        if type(saved.get("schema_version")) is not int or saved["schema_version"] != 2:
            raise CampaignIntegrityError(
                "checkpoint resume requires source-bound identity v2; v1 is ambiguous"
            )
        expected = expected_training_identity(
            binding=binding,
            config=config,
            dataset=dataset,
            source_revision=source_revision,
        )
        if saved != expected:
            raise CampaignIntegrityError(
                "checkpoint source/model/config/dataset identity differs"
            )
        return str(expected["training_identity"])
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, CampaignIntegrityError):
            raise
        raise CampaignIntegrityError(f"checkpoint identity is invalid: {exc}") from exc


@dataclass(frozen=True, slots=True)
class VerifiedTrainingReuse:
    result: JsonObject
    manifest: RunManifest
    training_identity: str


def verify_training_reuse(
    directory: str | Path,
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    source_revision: str,
) -> VerifiedTrainingReuse:
    """Verify exact experiment identity and artifacts before skipping training.

    Matching file hashes alone cannot establish that an existing adapter belongs
    to the requested dataset/mix. Check identity before returning its run ID.
    """
    root = Path(directory).resolve()
    try:
        if len(source_revision) != 40 or any(
            c not in "0123456789abcdef" for c in source_revision
        ):
            raise CampaignIntegrityError(
                "source revision must be a full immutable Git SHA"
            )
        result = _read(_artifact(root, "training-result.json"))
        saved_identity = _read(_artifact(root, "training-identity.json"))
        version = saved_identity.get("schema_version")
        if type(version) is not int or version not in {1, 2}:
            raise CampaignIntegrityError(
                "unsupported completed training identity version"
            )
        expected = expected_training_identity(
            binding=binding,
            config=config,
            dataset=dataset,
            source_revision=source_revision if version == 2 else None,
        )
        if saved_identity != expected:
            raise CampaignIntegrityError(
                "completed training model/config/dataset/source identity differs"
            )
        manifest_path = _artifact(root, "run-manifest.json")
        if sha256_file(manifest_path) != result.get("run_manifest_sha256"):
            raise CampaignIntegrityError("completed training run manifest hash differs")
        manifest = cast(
            RunManifest, load_record(_read(manifest_path), expected_type=RunManifest)
        )
        if manifest.git_commit != source_revision:
            raise CampaignIntegrityError("completed training source revision differs")
        generator = manifest.generator_config
        if (
            generator.get("phase") != "train-export"
            or generator.get("template_strategy") != config.template_strategy
        ):
            raise CampaignIntegrityError(
                "completed training phase/template identity differs"
            )
        for key, value in (
            ("model_binding", binding.to_object()),
            ("training_config", config.to_object()),
            ("dataset_identity", dataset.to_object()),
        ):
            if generator.get(key) != value:
                raise CampaignIntegrityError(
                    f"completed training manifest {key} differs"
                )
        expected_run_hash = content_hash(
            {
                "phase": "train-export",
                "model_binding": binding.to_object(),
                "training_config": config.to_object(),
                "dataset_identity": dataset.to_object(),
                "git_commit": source_revision,
                "backend": config.backend,
            }
        )
        expected_run_id = f"ttt-012-train-export-{expected_run_hash[:16]}"
        if (
            manifest.run_id != expected_run_id
            or result.get("run_id") != expected_run_id
        ):
            raise CampaignIntegrityError("completed training run identity differs")
        if (
            manifest.seeds != {"training": config.seed, "sampling_order": config.seed}
            or manifest.runtime.get("backend") != config.backend
            or manifest.runtime.get("parity_passed") is not True
            or manifest.runtime.get("training_identity")
            != expected["training_identity"]
        ):
            raise CampaignIntegrityError(
                "completed training seed/backend/parity identity differs"
            )
        adapter_dir = result.get("adapter_dir")
        if (
            not isinstance(adapter_dir, str)
            or Path(adapter_dir).resolve() != root / "adapter"
        ):
            raise CampaignIntegrityError("completed training adapter directory differs")
        hashes = require_json_object(
            result.get("artifact_hashes"), field="artifact_hashes"
        )
        if hashes != manifest.artifact_hashes:
            raise CampaignIntegrityError(
                "result and run manifest artifact inventories differ"
            )
        if not {"training-identity.json", "parity.json"} <= set(hashes) or not any(
            name.replace("\\", "/").startswith("adapter/") for name in hashes
        ):
            raise CampaignIntegrityError("completed training omits required artifacts")
        for name, digest in hashes.items():
            if sha256_file(_artifact(root, name)) != digest:
                raise CampaignIntegrityError(
                    f"completed training artifact hash differs: {name}"
                )
        declared_adapter = {
            name.replace("\\", "/")
            for name in hashes
            if name.replace("\\", "/").startswith("adapter/")
        }
        actual_adapter = {
            path.relative_to(root).as_posix()
            for path in (root / "adapter").rglob("*")
            if path.is_file()
        }
        if actual_adapter != declared_adapter:
            raise CampaignIntegrityError("adapter contains undeclared or missing files")
        parity = _read(_artifact(root, "parity.json"))
        cases = parity.get("cases")
        if (
            result.get("parity") != parity
            or parity.get("passed") is not True
            or not isinstance(cases, list)
            or not cases
            or not all(
                isinstance(case, dict) and case.get("equal") is True for case in cases
            )
        ):
            raise CampaignIntegrityError("completed training parity evidence differs")
        return VerifiedTrainingReuse(
            result, manifest, str(expected["training_identity"])
        )
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, CampaignIntegrityError):
            raise
        raise CampaignIntegrityError(
            f"completed training evidence is invalid: {exc}"
        ) from exc
