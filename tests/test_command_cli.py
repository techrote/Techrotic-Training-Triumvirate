from __future__ import annotations

import json

import pytest

from techrotic_training_triumvirate.cli import main
from techrotic_training_triumvirate.commands import COMMAND_PROTOCOL_VERSION


def test_cli_exports_deterministic_command_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["command-schema"]) == 0
    first = capsys.readouterr().out
    assert main(["command-schema"]) == 0
    second = capsys.readouterr().out

    assert first == second
    parsed = json.loads(first)
    assert COMMAND_PROTOCOL_VERSION in parsed["title"]
    assert len(parsed["oneOf"]) == 9
