from __future__ import annotations

import json

import pytest

from techrotic_training_triumvirate.cli import main


def test_world_demo_cli_is_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["world-demo", "--seed", "24301", "--turns", "24"]

    assert main(argv) == 0
    first = capsys.readouterr().out
    assert main(argv) == 0
    second = capsys.readouterr().out

    assert first == second
    payload = json.loads(first)
    assert payload["turns"] == 24
    assert payload["events"] >= 24
    assert "ROUTE_BLOCKED" in payload["failure_codes"]
    assert len(payload["final_state_hash"]) == 64
    assert len(payload["event_hash"]) == 64
