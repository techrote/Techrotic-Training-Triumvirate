"""First-class CPU GGUF conversion, Q4 quantization and inference diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from techrotic_training_triumvirate.schemas import JsonObject, canonical_json
from techrotic_training_triumvirate.training.export import sha256_file

from .adapters import (
    CpuDiagnosticSpec,
    PipelineAdapterError,
    run_cpu_diagnostic,
)
from .model import EvidenceClass


@dataclass(frozen=True, slots=True)
class CpuQ4QualificationSpec:
    """Three explicit CPU stages bound to one F16 and one Q4 artifact."""

    conversion: CpuDiagnosticSpec
    quantization: CpuDiagnosticSpec
    inference: CpuDiagnosticSpec
    f16_artifact: Path
    q4_artifact: Path
    output_dir: Path


def _require_success(name: str, result: JsonObject) -> None:
    if result.get("returncode") != 0:
        raise PipelineAdapterError(f"CPU {name} diagnostic returned non-zero")


def run_cpu_q4_qualification(spec: CpuQ4QualificationSpec) -> JsonObject:
    """Run conversion -> Q4 -> inference as permanently diagnostic evidence."""

    output = spec.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise PipelineAdapterError("CPU Q4 qualification output must be fresh")
    output.mkdir(parents=True, exist_ok=True)

    f16 = spec.f16_artifact.resolve()
    q4 = spec.q4_artifact.resolve()
    if spec.conversion.artifact is None or spec.conversion.artifact.resolve() != f16:
        raise PipelineAdapterError("conversion must declare the F16 GGUF artifact")
    if spec.quantization.artifact is None or spec.quantization.artifact.resolve() != q4:
        raise PipelineAdapterError("quantization must declare the Q4 GGUF artifact")

    conversion = run_cpu_diagnostic(spec.conversion)
    _require_success("conversion", conversion)
    if not f16.is_file() or f16.stat().st_size <= 0:
        raise PipelineAdapterError("conversion did not produce a non-empty F16 GGUF")
    f16_sha256 = sha256_file(f16)

    quantization = run_cpu_diagnostic(spec.quantization)
    _require_success("quantization", quantization)
    if sha256_file(f16) != f16_sha256:
        raise PipelineAdapterError("F16 GGUF changed during quantization")
    if not q4.is_file() or q4.stat().st_size <= 0:
        raise PipelineAdapterError("quantization did not produce a non-empty Q4 GGUF")
    q4_sha256 = sha256_file(q4)

    inference = run_cpu_diagnostic(spec.inference)
    _require_success("inference", inference)
    if sha256_file(q4) != q4_sha256:
        raise PipelineAdapterError("Q4 GGUF changed during inference")

    record: JsonObject = {
        "schema": "ttt.cpu_q4_qualification",
        "schema_version": 1,
        "evidence_class": EvidenceClass.CPU_DIAGNOSTIC.value,
        "admission_eligible": False,
        "named_host_acceptance": False,
        "f16": {
            "path": str(f16),
            "bytes": f16.stat().st_size,
            "sha256": f16_sha256,
        },
        "q4": {
            "path": str(q4),
            "bytes": q4.stat().st_size,
            "sha256": q4_sha256,
        },
        "stages": {
            "conversion": conversion,
            "quantization": quantization,
            "inference": inference,
        },
    }
    (output / "cpu-q4-qualification.json").write_text(
        canonical_json(record) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return record
