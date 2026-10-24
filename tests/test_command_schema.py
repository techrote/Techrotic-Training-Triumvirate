from __future__ import annotations

from techrotic_training_triumvirate.commands.model import (
    COMMAND_PROTOCOL_VERSION,
    Operation,
)
from techrotic_training_triumvirate.commands.schema import command_schema


def test_command_schema_is_versioned_and_covers_operation_family() -> None:
    schema = command_schema()

    assert COMMAND_PROTOCOL_VERSION in schema["title"]
    variants = schema["oneOf"]
    assert isinstance(variants, list)
    operations = {variant["properties"]["op"]["const"] for variant in variants}
    assert operations == {operation.value for operation in Operation}


def test_command_schema_closes_every_operation_body() -> None:
    variants = command_schema()["oneOf"]
    assert isinstance(variants, list)

    for variant in variants:
        assert variant["additionalProperties"] is False
        assert "observation_generation" in variant["required"]
        assert "op" in variant["required"]
