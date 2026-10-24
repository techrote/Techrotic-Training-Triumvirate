"""CPU-only conversion/Q4 diagnostic execution remains non-admission evidence."""

from __future__ import annotations

import sys
from pathlib import Path

from techrotic_training_triumvirate.experiments import (
    CpuQualificationSpec,
    run_cpu_qualification,
)


def test_cpu_qualification_runs_real_bounded_subprocesses_but_is_diagnostic(
    tmp_path: Path,
) -> None:
    f16 = tmp_path / "model-f16.gguf"
    q4 = tmp_path / "model-q4.gguf"
    converter = (
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(f16)!r}).write_bytes(b'f16-gguf')",
    )
    quantizer = (
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(q4)!r}).write_bytes(b'q4-gguf')",
    )
    inference = (
        sys.executable,
        "-c",
        "print('deterministic q4 inference fixture')",
    )
    spec = CpuQualificationSpec(
        converter_argv=converter,
        quantizer_argv=quantizer,
        inference_argv=inference,
        required_paths=(),
        f16_gguf=str(f16),
        q4_gguf=str(q4),
        output_dir=str(tmp_path),
        threads=1,
        timeout_seconds=10,
    )
    result = run_cpu_qualification(spec)
    assert result["available"] is True
    assert result["evidence_class"] == "cpu_diagnostic"
    assert result["admission_substitute"] is False
    assert result["named_host_acceptance"] is False
    assert result["f16"]["bytes"] > 0
    assert result["q4"]["bytes"] > 0
    assert (tmp_path / "inference.stdout.log").read_text().strip()


def test_cpu_qualification_cleanly_records_unavailable_tooling(tmp_path: Path) -> None:
    missing = ("definitely-not-a-real-ttt-binary",)
    spec = CpuQualificationSpec(
        converter_argv=missing,
        quantizer_argv=missing,
        inference_argv=missing,
        required_paths=(),
        f16_gguf=str(tmp_path / "f16.gguf"),
        q4_gguf=str(tmp_path / "q4.gguf"),
        output_dir=str(tmp_path),
    )
    result = run_cpu_qualification(spec)
    assert result == {
        "schema": "ttt.cpu_q4_diagnostic",
        "schema_version": 1,
        "available": False,
        "evidence_class": "cpu_diagnostic",
        "admission_substitute": False,
        "named_host_acceptance": False,
    }
