"""CPU diagnostic and admission-boundary regression tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from techrotic_training_triumvirate.experiments import (
    CpuDiagnosticSpec,
    PipelineAdapterError,
    assert_admission_eligible,
    run_cpu_diagnostic,
)


def test_real_cpu_tool_execution_is_recorded_but_never_admission_evidence(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "candidate.gguf"
    record = run_cpu_diagnostic(
        CpuDiagnosticSpec(
            tool=Path(sys.executable),
            args=(
                "-c",
                "from pathlib import Path; Path('candidate.gguf').write_bytes(b'GGUF')",
            ),
            cwd=tmp_path,
            output_dir=tmp_path / "diagnostic",
            timeout_seconds=10,
            artifact=artifact,
        )
    )
    assert record["returncode"] == 0
    assert record["evidence_class"] == "cpu-diagnostic"
    assert record["admission_eligible"] is False
    assert record["artifact"]["bytes"] == 4
    with pytest.raises(PipelineAdapterError, match="cannot satisfy admission"):
        assert_admission_eligible(record)


def test_cpu_diagnostic_requires_fresh_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "diagnostic"
    output.mkdir()
    (output / "old.txt").write_text("old", encoding="utf-8")
    with pytest.raises(PipelineAdapterError, match="fresh"):
        run_cpu_diagnostic(
            CpuDiagnosticSpec(
                tool=Path(sys.executable),
                args=("-c", "print('no')"),
                cwd=tmp_path,
                output_dir=output,
                timeout_seconds=10,
            )
        )
