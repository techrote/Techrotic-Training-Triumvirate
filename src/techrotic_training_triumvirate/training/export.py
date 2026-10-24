"""Artifact export, run manifests, and inference-parity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.schemas import JsonObject, RunManifest, canonical_json

from .admission import quantization_export_spec
from .model import (
    BudgetAuthorization,
    DatasetIdentity,
    MappedExample,
    ModelBinding,
    TinyTrainingResult,
    TrainingConfig,
)
from .tiny import predict_tiny


class TrainingExportError(ValueError):
    """Raised when a training artifact cannot be exported safely."""


def sha256_file(path: str | Path) -> str:
    """Hash one artifact exactly as stored."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: JsonObject) -> None:
    path.write_text(
        f"{canonical_json(value)}\n",
        encoding="utf-8",
        newline="\n",
    )


def build_run_manifest(
    *,
    phase: str,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    git_commit: str,
    artifact_hashes: JsonObject,
    backend: str,
    budget: BudgetAuthorization | None,
    command_line: tuple[str, ...],
    parent_run_ids: tuple[str, ...] = (),
    extra_runtime: JsonObject | None = None,
) -> RunManifest:
    """Build the canonical TTT run manifest for training or export."""

    identity_payload: JsonObject = {
        "phase": phase,
        "model_binding": binding.to_object(),
        "training_config": config.to_object(),
        "dataset_identity": dataset.to_object(),
        "git_commit": git_commit,
        "backend": backend,
    }
    run_hash = hashlib.sha256(canonical_json(identity_payload).encode()).hexdigest()
    runtime: JsonObject = {
        "backend": backend,
        "heavy_training": budget is not None,
        "budget": budget.to_object() if budget is not None else None,
        "started_at": None,
        "finished_at": None,
    }
    if extra_runtime:
        runtime.update(extra_runtime)

    return RunManifest(
        run_id=f"ttt-012-{phase}-{run_hash[:16]}",
        git_commit=git_commit,
        schema_versions={
            "ttt.run_manifest": 1,
            "ttt.training_export": 1,
        },
        seeds={"training": config.seed, "sampling_order": config.seed},
        generator_config={
            "phase": phase,
            "model_binding": binding.to_object(),
            "training_config": config.to_object(),
            "dataset_identity": dataset.to_object(),
            "template_strategy": config.template_strategy,
        },
        source_refs=(
            f"model-cast:{binding.model_cast_sha256}",
            f"dataset-manifest:{dataset.manifest_sha256}",
            f"dataset:{dataset.dataset_hash}",
        ),
        parent_run_ids=parent_run_ids,
        artifact_hashes=artifact_hashes,
        command_line=command_line,
        runtime=runtime,
    )


def _load_tiny_memory(path: Path) -> dict[str, str]:
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise TrainingExportError("exported tiny adapter is malformed")
    data = cast(dict[str, Any], parsed)
    raw_memory = data.get("memory")
    if not isinstance(raw_memory, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in raw_memory.items()
    ):
        raise TrainingExportError("exported tiny adapter memory is malformed")
    return dict(cast(dict[str, str], raw_memory))


def export_tiny(
    result: TinyTrainingResult,
    mapped: tuple[MappedExample, ...],
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    output_dir: str | Path,
    git_commit: str,
) -> JsonObject:
    """Export a reloadable tiny artifact and prove fixed-fixture parity."""

    if not result.complete:
        raise TrainingExportError("cannot export an incomplete smoke checkpoint")

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    adapter_path = root / "adapter.json"
    tokenizer_path = root / "tokenizer-config.json"
    template_path = root / "template-config.json"
    config_path = root / "training-config.json"
    dataset_path = root / "dataset-identity.json"
    binding_path = root / "model-binding.json"
    quant_path = root / "quantization-spec.json"
    parity_path = root / "parity.json"

    _write_json(
        adapter_path,
        {
            "schema_version": 1,
            "backend": "tiny-deterministic-v1",
            "training_identity": result.training_identity,
            "model_hash": result.model_hash,
            "memory": dict(result.memory),
        },
    )
    _write_json(
        tokenizer_path,
        {
            "strategy": "native-tokenizer-delegated",
            "model_key": binding.model_key,
            "native_repository": binding.native_repository,
            "native_revision": binding.native_revision,
        },
    )
    _write_json(
        template_path,
        {
            "strategy": config.template_strategy,
            "recorded_chat_format": binding.tokenizer_chat_format,
        },
    )
    _write_json(config_path, config.to_object())
    _write_json(dataset_path, dataset.to_object())
    _write_json(binding_path, binding.to_object())
    _write_json(quant_path, quantization_export_spec(binding.model_key))

    exported_memory = _load_tiny_memory(adapter_path)
    parity_cases: list[JsonObject] = []
    passed = True
    for example in mapped:
        before = predict_tiny(result, example)
        prompt_hash = hashlib.sha256(
            canonical_json(
                [item.to_object() for item in example.prompt_messages]
            ).encode()
        ).hexdigest()
        after = exported_memory.get(prompt_hash, "")
        equal = before == after
        passed = passed and equal
        parity_cases.append(
            {
                "example_id": example.example_id,
                "pre_export_sha256": hashlib.sha256(before.encode()).hexdigest(),
                "exported_sha256": hashlib.sha256(after.encode()).hexdigest(),
                "equal": equal,
            }
        )
    parity: JsonObject = {
        "schema_version": 1,
        "passed": passed,
        "case_count": len(parity_cases),
        "cases": parity_cases,
    }
    _write_json(parity_path, parity)
    if not passed:
        raise TrainingExportError("tiny export inference parity failed")

    artifact_paths = (
        adapter_path,
        tokenizer_path,
        template_path,
        config_path,
        dataset_path,
        binding_path,
        quant_path,
        parity_path,
    )
    artifact_hashes: JsonObject = {
        path.name: sha256_file(path) for path in artifact_paths
    }
    run_manifest = build_run_manifest(
        phase="export",
        binding=binding,
        config=config,
        dataset=dataset,
        git_commit=git_commit,
        artifact_hashes=artifact_hashes,
        backend="tiny-deterministic-v1",
        budget=None,
        command_line=(
            "ttt-train",
            "smoke",
            "--model",
            binding.model_key,
            "--mix",
            config.mix.value,
            "--seed",
            str(config.seed),
        ),
        extra_runtime={"parity_passed": True},
    )
    run_manifest_path = root / "run-manifest.json"
    run_manifest_path.write_text(
        f"{run_manifest.to_json()}\n",
        encoding="utf-8",
        newline="\n",
    )
    artifact_hashes["run-manifest.json"] = sha256_file(run_manifest_path)

    export_manifest: JsonObject = {
        "manifest_version": 1,
        "model_key": binding.model_key,
        "base_model_identity": binding.to_object(),
        "dataset_identity": dataset.to_object(),
        "training_config": config.to_object(),
        "tiny_model_hash": result.model_hash,
        "artifact_hashes": artifact_hashes,
        "parity": parity,
        "quantization": quantization_export_spec(binding.model_key),
    }
    _write_json(root / "export-manifest.json", export_manifest)
    return export_manifest
