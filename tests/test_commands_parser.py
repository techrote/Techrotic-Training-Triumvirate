from __future__ import annotations

import pytest

from techrotic_training_triumvirate.commands import (
    COMMAND_PROTOCOL_VERSION,
    AssignObjectiveCommand,
    CancelCommand,
    CommandParseError,
    CoordinateCommand,
    ErrorCode,
    HoldCommand,
    InspectCommand,
    RecallCommand,
    RequestStatusCommand,
    SetConstraintsCommand,
    TransmitCommand,
    parse_command_envelope,
    parse_model_command,
)


@pytest.mark.parametrize(
    ("body", "expected_type"),
    [
        (
            {
                "op": "inspect",
                "observation_generation": 4,
                "entity_id": "squad-a",
                "fields": ["status"],
            },
            InspectCommand,
        ),
        (
            {
                "op": "assign_objective",
                "observation_generation": 4,
                "unit_id": "squad-a",
                "objective_kind": "flank",
                "target_id": "relay",
                "approach": "north",
                "constraints": ["avoid:flooded"],
            },
            AssignObjectiveCommand,
        ),
        (
            {
                "op": "set_constraints",
                "observation_generation": 4,
                "unit_id": "squad-a",
                "constraints": {"urgency": "high"},
            },
            SetConstraintsCommand,
        ),
        (
            {
                "op": "coordinate",
                "observation_generation": 4,
                "unit_ids": ["squad-a", "squad-b"],
                "trigger": "on-contact",
                "objective_id": "relay",
            },
            CoordinateCommand,
        ),
        (
            {
                "op": "hold",
                "observation_generation": 4,
                "unit_id": "squad-a",
            },
            HoldCommand,
        ),
        (
            {
                "op": "cancel",
                "observation_generation": 4,
                "unit_id": "squad-a",
                "order_id": "order-1",
            },
            CancelCommand,
        ),
        (
            {
                "op": "recall",
                "observation_generation": 4,
                "unit_id": "squad-a",
                "destination_id": "staging",
            },
            RecallCommand,
        ),
        (
            {
                "op": "transmit",
                "observation_generation": 4,
                "recipients": ["squad-a"],
                "channel": "radio",
                "message": "advance",
            },
            TransmitCommand,
        ),
        (
            {
                "op": "request_status",
                "observation_generation": 4,
                "entity_ids": ["squad-a"],
            },
            RequestStatusCommand,
        ),
    ],
)
def test_all_v1_operations_parse(body: dict[str, object], expected_type: type) -> None:
    command = parse_model_command(body, command_id="cmd-1")

    assert isinstance(command, expected_type)
    assert command.command_id == "cmd-1"
    assert command.observation_generation == 4
    reparsed = parse_command_envelope(command.to_envelope())
    assert reparsed == command


def test_json_text_parses_to_typed_command() -> None:
    command = parse_model_command(
        '{"op":"hold","observation_generation":2,"unit_id":"unit-a"}',
        command_id="cmd-json",
    )

    assert isinstance(command, HoldCommand)
    assert command.unit_id == "unit-a"


@pytest.mark.parametrize(
    "value",
    [
        "not json",
        {"op": "shell", "observation_generation": 1, "program": "bash"},
        {
            "op": "hold",
            "observation_generation": 1,
            "unit_id": "unit-a",
            "shell": "rm -rf /",
        },
        {
            "op": "hold",
            "observation_generation": -1,
            "unit_id": "unit-a",
        },
    ],
)
def test_malformed_or_executable_shaped_commands_refuse(value: object) -> None:
    with pytest.raises(CommandParseError) as exc_info:
        parse_model_command(value, command_id="bad")

    assert exc_info.value.code is ErrorCode.SCHEMA_INVALID


def test_command_protocol_version_is_independent_and_strict() -> None:
    command = HoldCommand(
        command_id="cmd-version",
        observation_generation=1,
        unit_id="unit-a",
    )
    envelope = command.to_envelope()
    assert envelope.protocol_version == COMMAND_PROTOCOL_VERSION

    wrong = type(envelope)(
        command_id=envelope.command_id,
        protocol_version="ttt-command-v999",
        body=envelope.body,
    )
    with pytest.raises(CommandParseError) as exc_info:
        parse_command_envelope(wrong)

    assert exc_info.value.code is ErrorCode.PROTOCOL_UNSUPPORTED
