"""Adapters from the controller to existing TTT validation and evidence machinery."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from techrotic_training_triumvirate.admission import verify_package
from techrotic_training_triumvirate.runtime import load_tiny_export
from techrotic_training_triumvirate.schemas import JsonObject, JsonValue, canonical_json
from techrotic_training_triumvirate.training.campaign_integrity import (
    verify_checkpoint_identity,
    verify_training_reuse,
)
from techrotic_training_triumvirate.training.data import load_corpus_examples
from techrotic_training_triumvirate.training.export import sha256_file
from techrotic_training_triumvirate.training.model import (
    DatasetIdentity,
    ModelBinding,
    TrainingConfig,
)

from .model import EvidenceClass


class PipelineAdapterError(ValueError):
    """A pipeline artifact or diagnostic cannot satisfy its declared contract."""


@dataclass(frozen=True, slots=True)
class CpuDiagnosticSpec:
    """One fixed argv CPU diagnostic. No shell or model-authored command is accepted."""

    tool: Path
    args: tuple[str, ...]
    cwd: Path
    output_dir: Path
    timeout_seconds: float
    artifact: Path | None = None
    threads: int = 2
    low_priority: bool = True


def verify_corpus(corpus_dir: str | Path) -> JsonObject:
    """Reuse the canonical shard/hash/split validator before orchestration."""

    examples, identity = load_corpus_examples(corpus_dir)
    return {
        "example_count": len(examples),
        "dataset_identity": identity.to_object(),
        "verified": True,
    }


def verify_checkpoint(
    directory: str | Path,
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    source_revision: str,
) -> JsonObject:
    """Reject stale checkpoint resume before any training backend loads it."""

    identity = verify_checkpoint_identity(
        directory,
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=source_revision,
    )
    return {"verified": True, "training_identity": identity}


def verify_training(
    directory: str | Path,
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    source_revision: str,
) -> JsonObject:
    """Reuse exact source/model/config/data/parity readback for completed training."""

    result = verify_training_reuse(
        directory,
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=source_revision,
    )
    return {
        "verified": True,
        "run_id": result.manifest.run_id,
        "training_identity": result.training_identity,
        "artifact_hashes": result.manifest.artifact_hashes,
    }


def verify_export(directory: str | Path) -> JsonObject:
    """Reuse the existing dependency-free export/parity validator."""

    export = load_tiny_export(directory)
    return {
        "verified": True,
        "manifest_sha256": export.manifest_sha256,
        "model_key": export.model_key,
        "base_model_identity": export.base_model_identity,
    }


def verify_admission(package: str | Path, *, evidence_root: str | Path) -> JsonObject:
    """Delegate final disposition to the existing strict admission verifier."""

    return verify_package(package, evidence_root=evidence_root)


def assert_admission_eligible(record: JsonObject) -> None:
    """Prevent simulated or CPU-diagnostic records from satisfying real admission."""

    if (
        record.get("evidence_class") != EvidenceClass.ADMISSION.value
        or record.get("admission_eligible") is not True
    ):
        raise PipelineAdapterError(
            "simulation/CPU diagnostic evidence cannot satisfy admission"
        )


def _lower_priority() -> None:
    with suppress(OSError):
        os.nice(10)


def run_cpu_diagnostic(spec: CpuDiagnosticSpec) -> JsonObject:
    """Execute an available conversion/inference tool as non-admission evidence.

    This path can exercise real GGUF conversion or Q4 inference when the operator
    supplies the exact local executable and arguments. Its output is deliberately
    marked diagnostic so CPU measurements can never substitute for named-host
    acceptance evidence.
    """

    tool = spec.tool.resolve()
    cwd = spec.cwd.resolve()
    output = spec.output_dir.resolve()
    if not tool.is_file() or not tool.is_absolute():
        raise PipelineAdapterError(
            "CPU diagnostic tool must be an existing absolute file"
        )
    if not cwd.is_dir():
        raise PipelineAdapterError("CPU diagnostic cwd must be an existing directory")
    if (
        not isinstance(spec.timeout_seconds, (int, float))
        or isinstance(spec.timeout_seconds, bool)
        or not 0 < float(spec.timeout_seconds) <= 3600
    ):
        raise PipelineAdapterError("CPU diagnostic timeout must be in (0, 3600]")
    if type(spec.threads) is not int or not 1 <= spec.threads <= 64:
        raise PipelineAdapterError("CPU diagnostic threads must be in [1, 64]")
    if type(spec.low_priority) is not bool:
        raise PipelineAdapterError("CPU diagnostic low_priority must be boolean")
    if output.exists() and any(output.iterdir()):
        raise PipelineAdapterError("CPU diagnostic output directory must be fresh")
    output.mkdir(parents=True, exist_ok=True)

    environment = dict(os.environ)
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "GGML_CUDA": "0",
            "OMP_NUM_THREADS": str(spec.threads),
            "MKL_NUM_THREADS": str(spec.threads),
        }
    )
    creationflags = 0
    preexec_fn: Callable[[], None] | None = None
    if spec.low_priority:
        if os.name == "nt":
            creationflags = int(
                getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
            )
        else:
            preexec_fn = _lower_priority

    stdout_path = output / "stdout.log"
    stderr_path = output / "stderr.log"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [str(tool), *spec.args],
            cwd=cwd,
            capture_output=True,
            check=False,
            timeout=float(spec.timeout_seconds),
            env=environment,
            creationflags=creationflags,
            preexec_fn=preexec_fn,
        )
    except subprocess.TimeoutExpired as exc:
        raise PipelineAdapterError("CPU diagnostic exceeded its hard timeout") from exc
    elapsed = time.monotonic() - started
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)

    artifact: JsonObject | None = None
    if spec.artifact is not None:
        artifact_path = spec.artifact.resolve()
        if not artifact_path.is_file():
            raise PipelineAdapterError(
                "CPU diagnostic did not produce the declared artifact"
            )
        artifact = {
            "path": str(artifact_path),
            "bytes": artifact_path.stat().st_size,
            "sha256": sha256_file(artifact_path),
        }

    argv: list[JsonValue] = [str(tool), *spec.args]
    record: JsonObject = {
        "schema": "ttt.cpu_diagnostic",
        "schema_version": 1,
        "evidence_class": EvidenceClass.CPU_DIAGNOSTIC.value,
        "admission_eligible": False,
        "tool": str(tool),
        "tool_sha256": sha256_file(tool),
        "argv": argv,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "artifact": artifact,
        "cpu_threads": spec.threads,
        "priority": "low" if spec.low_priority else "normal",
        "named_host_acceptance": False,
        "host": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
    }
    (output / "diagnostic.json").write_text(
        canonical_json(record) + "\n", encoding="utf-8", newline="\n"
    )
    return record


def load_review(path: str | Path) -> JsonObject:
    """Load a small supplied review object without generating or inferring ratings."""

    try:
        value: object = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineAdapterError(f"cannot read supplied review: {exc}") from exc
    if not isinstance(value, dict):
        raise PipelineAdapterError("supplied review must be an object")
    return cast(JsonObject, value)
