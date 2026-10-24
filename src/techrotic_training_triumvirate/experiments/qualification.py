"""Bounded CPU GGUF/Q4 diagnostics that never substitute for named-host acceptance."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from techrotic_training_triumvirate.schemas import JsonObject
from techrotic_training_triumvirate.training.export import sha256_file

from .model import EvidenceClass, OrchestrationError


class CpuQualificationError(OrchestrationError):
    """CPU export or Q4 diagnostic execution failed."""


def _command_available(argv: tuple[str, ...]) -> bool:
    if not argv:
        return False
    executable = argv[0]
    path = Path(executable)
    if path.parent != Path(".") or path.is_absolute():
        return path.is_file()
    return shutil.which(executable) is not None


@dataclass(frozen=True, slots=True)
class CpuQualificationSpec:
    """Exact CPU-only commands and expected artifacts for a diagnostic run."""

    converter_argv: tuple[str, ...]
    quantizer_argv: tuple[str, ...]
    inference_argv: tuple[str, ...]
    required_paths: tuple[str, ...]
    f16_gguf: str
    q4_gguf: str
    output_dir: str
    threads: int = 2
    timeout_seconds: int = 900

    def __post_init__(self) -> None:
        if (
            not self.converter_argv
            or not self.quantizer_argv
            or not self.inference_argv
        ):
            raise CpuQualificationError("CPU qualification commands must be nonempty")
        if self.threads <= 0 or self.timeout_seconds <= 0:
            raise CpuQualificationError("CPU limits must be positive")
        for field_name, value in (
            ("f16_gguf", self.f16_gguf),
            ("q4_gguf", self.q4_gguf),
            ("output_dir", self.output_dir),
        ):
            if not value or "\x00" in value:
                raise CpuQualificationError(f"{field_name} must be a safe string")

    @classmethod
    def from_commands(
        cls,
        *,
        converter_argv: list[str],
        quantizer_argv: list[str],
        inference_argv: list[str],
        required_paths: list[str],
        f16_gguf: str,
        q4_gguf: str,
        output_dir: str,
        threads: int = 2,
        timeout_seconds: int = 900,
    ) -> Self:
        return cls(
            converter_argv=tuple(converter_argv),
            quantizer_argv=tuple(quantizer_argv),
            inference_argv=tuple(inference_argv),
            required_paths=tuple(required_paths),
            f16_gguf=f16_gguf,
            q4_gguf=q4_gguf,
            output_dir=output_dir,
            threads=threads,
            timeout_seconds=timeout_seconds,
        )

    def available(self) -> bool:
        return (
            all(
                _command_available(command)
                for command in (
                    self.converter_argv,
                    self.quantizer_argv,
                    self.inference_argv,
                )
            )
            and all(Path(path).exists() for path in self.required_paths)
        )


def _run_stage(
    name: str,
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: int,
) -> JsonObject:
    stdout_path = cwd / f"{name}.stdout.log"
    stderr_path = cwd / f"{name}.stderr.log"
    started = time.monotonic()
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            completed = subprocess.run(
                list(argv),
                cwd=str(cwd),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                check=False,
                timeout=timeout_seconds,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CpuQualificationError(f"{name} failed to execute: {exc}") from exc
    elapsed = max(0.0, time.monotonic() - started)
    if completed.returncode != 0:
        raise CpuQualificationError(
            f"{name} returned {completed.returncode}; see diagnostic logs"
        )
    return {
        "argv": list(argv),
        "returncode": completed.returncode,
        "wall_seconds": elapsed,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
    }


def run_cpu_qualification(spec: CpuQualificationSpec) -> JsonObject:
    """Execute real CPU conversion/quantization/inference when tools are present.

    The resulting record is deliberately CPU_DIAGNOSTIC. It cannot satisfy the
    named-host Q4 runtime gate in a substantive experiment.
    """

    if not spec.available():
        return {
            "schema": "ttt.cpu_q4_diagnostic",
            "schema_version": 1,
            "available": False,
            "evidence_class": EvidenceClass.CPU_DIAGNOSTIC.value,
            "admission_substitute": False,
            "named_host_acceptance": False,
        }

    output = Path(spec.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "GGML_CUDA": "0",
            "OMP_NUM_THREADS": str(spec.threads),
        }
    )
    conversion = _run_stage(
        "convert",
        spec.converter_argv,
        cwd=output,
        environment=environment,
        timeout_seconds=spec.timeout_seconds,
    )
    f16 = Path(spec.f16_gguf).resolve()
    if not f16.is_file() or f16.stat().st_size <= 0:
        raise CpuQualificationError("converter did not produce the declared F16 GGUF")
    quantization = _run_stage(
        "quantize",
        spec.quantizer_argv,
        cwd=output,
        environment=environment,
        timeout_seconds=spec.timeout_seconds,
    )
    q4 = Path(spec.q4_gguf).resolve()
    if not q4.is_file() or q4.stat().st_size <= 0:
        raise CpuQualificationError("quantizer did not produce the declared Q4 GGUF")
    inference = _run_stage(
        "inference",
        spec.inference_argv,
        cwd=output,
        environment=environment,
        timeout_seconds=spec.timeout_seconds,
    )
    return {
        "schema": "ttt.cpu_q4_diagnostic",
        "schema_version": 1,
        "available": True,
        "evidence_class": EvidenceClass.CPU_DIAGNOSTIC.value,
        "admission_substitute": False,
        "named_host_acceptance": False,
        "host": {
            "node": platform.node(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "limits": {
            "threads": spec.threads,
            "timeout_seconds": spec.timeout_seconds,
        },
        "f16": {
            "path": str(f16),
            "bytes": f16.stat().st_size,
            "sha256": sha256_file(f16),
        },
        "q4": {
            "path": str(q4),
            "bytes": q4.stat().st_size,
            "sha256": sha256_file(q4),
        },
        "stages": {
            "conversion": conversion,
            "quantization": quantization,
            "inference": inference,
        },
    }
