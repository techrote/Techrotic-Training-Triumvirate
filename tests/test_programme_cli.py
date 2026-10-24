"""User-facing end-to-end controls require no models or network access."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.cli import main


def test_runtime_cli_writes_grounded_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "runtime.json"
    assert main(["runtime-demo", "--turns", "4", "--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert json.loads(capsys.readouterr().out) == report
    assert report["runtime_protocol"] == "ttt-runtime-v1"
    assert len(report["turns"]) == 4
    assert any(turn["intercepts"] for turn in report["turns"])


def test_runtime_cli_refuses_unbounded_session(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as failure:
        main(["runtime-demo", "--turns", "1000000"])
    assert failure.value.code == 1
    assert "between 1 and 256" in capsys.readouterr().err


def test_closed_loop_cli_round_trip_and_corruption(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["closed-loop", "--output", str(tmp_path), "--code-revision", "a" * 40])
        == 0
    )
    capsys.readouterr()
    report = tmp_path / "candidate-01.json"
    argv = ["closed-loop-verify", "--report", str(report)]
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True
    value = json.loads(report.read_text())
    value["evidence"]["episodes"][0]["final_world_hash"] = "0" * 64
    report.write_text(json.dumps(value))
    with pytest.raises(SystemExit) as failure:
        main(argv)
    assert failure.value.code == 1
    assert "hash mismatch" in capsys.readouterr().err


def test_frozen_evaluation_cli_writes_both_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["evaluate", "--output", str(tmp_path), "--code-revision", "a" * 40]) == 0
    )
    assert len(json.loads(capsys.readouterr().out)["report_hash"]) == 64
    report = json.loads((tmp_path / "frozen-evaluation.json").read_text())
    assert report["benchmark_id"] == "ttt-core-frozen"
    assert report["code_revision"] == "a" * 40
    assert (tmp_path / "frozen-evaluation.md").is_file()
