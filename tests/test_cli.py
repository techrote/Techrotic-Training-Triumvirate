from __future__ import annotations

import json

import pytest

from techrotic_training_triumvirate.cli import main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Techrotic Training Triumvirate developer CLI." in output
    assert "seed-demo" in output


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "ttt 0.1.0"


def test_cli_seed_demo_is_deterministic(
    capsys: pytest.CaptureFixture[str],
    deterministic_seed: int,
) -> None:
    argv = ["seed-demo", "--seed", str(deterministic_seed), "--count", "3"]

    assert main(argv) == 0
    first = capsys.readouterr().out
    assert main(argv) == 0
    second = capsys.readouterr().out

    assert first == second
    payload = json.loads(first)
    assert payload["seed"] == deterministic_seed
    assert payload["count"] == 3
    assert len(payload["values"]) == 3
