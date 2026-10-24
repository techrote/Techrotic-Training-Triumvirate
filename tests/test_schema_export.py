from __future__ import annotations

import json

import pytest

from techrotic_training_triumvirate.cli import main
from techrotic_training_triumvirate.schemas import (
    registered_record_types,
    schema_bundle,
)


def test_schema_bundle_covers_every_registered_record() -> None:
    bundle = schema_bundle()
    definitions = bundle["$defs"]

    assert isinstance(definitions, dict)
    assert set(definitions) == set(registered_record_types())
    assert bundle["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_exported_envelopes_are_closed_and_versioned() -> None:
    definitions = schema_bundle()["$defs"]
    assert isinstance(definitions, dict)

    for name, definition in definitions.items():
        assert isinstance(definition, dict)
        assert definition["additionalProperties"] is False
        properties = definition["properties"]
        assert isinstance(properties, dict)
        assert properties["schema"] == {"const": name}
        assert properties["schema_version"] == {"const": 1}
        payload = properties["payload"]
        assert isinstance(payload, dict)
        assert payload["additionalProperties"] is False


def test_cli_exports_machine_readable_schema_bundle(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["schema-bundle"]) == 0
    first = capsys.readouterr().out
    assert main(["schema-bundle"]) == 0
    second = capsys.readouterr().out

    assert first == second
    parsed = json.loads(first)
    assert parsed["$defs"]["ttt.episode"]["properties"]["schema_version"] == {
        "const": 1
    }
