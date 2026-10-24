"""Bounded strict runtime wire parsing and endpoint trust boundaries."""

from __future__ import annotations

import copy
import json

import pytest

from techrotic_training_triumvirate.evaluation.baselines import (
    ScriptedCommanderBaseline,
)
from techrotic_training_triumvirate.runtime import (
    RuntimeHost,
    RuntimeLimits,
    RuntimeProtocolError,
    bounded_json,
    default_runtime_persona,
    parse_runtime_message,
    runtime_message,
)
from techrotic_training_triumvirate.schemas import AssistantAction


def _reset() -> dict[str, object]:
    return dict(
        runtime_message(
            "reset",
            session_id="session",
            sequence=0,
            payload={"seed": 24301, "persona": default_runtime_persona().to_dict()},
        ).to_dict()
    )


def test_runtime_canonical_json_round_trip_and_input_aliasing() -> None:
    raw = _reset()
    parsed = parse_runtime_message(raw)
    assert parse_runtime_message(parsed.to_json()) == parsed
    assert parse_runtime_message(parsed.to_json().encode()) == parsed
    original = parsed.to_json()
    raw["payload"] = {"injected": "different"}
    assert parsed.to_json() == original


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "ttt.unknown"),
        ("schema_version", 2),
        ("schema_version", True),
        ("protocol_version", "ttt-runtime-v2"),
        ("kind", "shell"),
        ("session_id", ""),
        ("session_id", "x" * 129),
        ("request_id", "bad\nID"),
        ("sequence", -1),
        ("sequence", True),
        ("extra", "unrecognized"),
    ],
)
def test_runtime_refuses_incompatible_envelope(field: str, value: object) -> None:
    raw = _reset()
    raw[field] = value
    with pytest.raises(RuntimeProtocolError):
        parse_runtime_message(raw)


@pytest.mark.parametrize(
    "value",
    [
        b"\xff",
        "{invalid",
        '{"a": 1, "a": 2}',
        '{"a": NaN}',
        '{"a": Infinity}',
        {"a": 2**63},
        {"a": object()},
        {1: "bad"},
    ],
)
def test_bounded_json_refuses_ambiguous_or_non_json_values(value: object) -> None:
    with pytest.raises(RuntimeProtocolError):
        bounded_json(value)


def test_runtime_bounds_bytes_depth_nodes_strings_and_collections() -> None:
    with pytest.raises(RuntimeProtocolError, match="byte limit"):
        bounded_json(" " * 65_537)
    with pytest.raises(RuntimeProtocolError, match="depth"):
        bounded_json("[" * 30 + "0" + "]" * 30)
    with pytest.raises(RuntimeProtocolError, match="collection"):
        bounded_json([0] * 257)
    with pytest.raises(RuntimeProtocolError, match="string"):
        bounded_json({"a": "é" * 8_193})
    with pytest.raises(RuntimeProtocolError, match="node"):
        bounded_json([0] * 10, limits=RuntimeLimits(max_nodes=5))
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(RuntimeProtocolError):
        bounded_json(cyclic)


def test_runtime_refuses_unknown_nested_fields_and_nested_schema_versions() -> None:
    raw = _reset()
    payload = copy.deepcopy(raw["payload"])
    assert isinstance(payload, dict)
    payload["extra"] = True
    raw["payload"] = payload
    with pytest.raises(RuntimeProtocolError):
        parse_runtime_message(raw)
    raw = _reset()
    text = json.dumps(raw).replace('"ttt.persona"', '"ttt.world_private_reference"')
    with pytest.raises(RuntimeProtocolError):
        parse_runtime_message(text)
    text = json.dumps(raw).replace('"schema_version": 1', '"schema_version": 99')
    with pytest.raises(RuntimeProtocolError):
        parse_runtime_message(text)


def test_host_negotiates_capabilities_and_refuses_unsupported_versions() -> None:
    host = RuntimeHost(ScriptedCommanderBaseline())
    request = runtime_message(
        "health_request",
        session_id="health",
        sequence=0,
        payload={
            "runtime_protocol_versions": ["ttt-runtime-v1"],
            "command_protocol_versions": ["ttt-command-v1"],
        },
    )
    health = host.handle(request)
    assert health.kind == "health"
    assert health.payload["model_artifact"] is None
    assert health.payload["policy"] == {
        "policy_id": "scripted-commander",
        "adapter_id": "deterministic-baseline",
        "revision": "v1",
    }
    assert health.payload["limits"] == RuntimeLimits().to_dict()
    bad = request.to_dict()
    bad["payload"] = {
        "runtime_protocol_versions": ["ttt-runtime-v9"],
        "command_protocol_versions": ["ttt-command-v1"],
    }
    with pytest.raises(RuntimeProtocolError, match="mutually supported"):
        host.handle(bad)


def test_model_host_refuses_authority_messages_and_nonzero_reset_sequence() -> None:
    host = RuntimeHost(ScriptedCommanderBaseline())
    action = runtime_message(
        "action",
        session_id="session",
        sequence=1,
        payload={"action": AssistantAction((), ()).to_dict()},
    )
    with pytest.raises(RuntimeProtocolError, match="accepts only"):
        host.handle(action)
    bad = _reset()
    bad["sequence"] = 1
    with pytest.raises(RuntimeProtocolError, match="sequence zero"):
        host.handle(bad)


def test_model_action_cannot_contain_authoritative_success_or_shell_operations() -> (
    None
):
    raw = AssistantAction((), ()).to_dict()
    payload = raw["payload"]
    assert isinstance(payload, dict)
    payload["accepted"] = True
    with pytest.raises(RuntimeProtocolError):
        runtime_message("action", session_id="s", sequence=1, payload={"action": raw})
    payload.pop("accepted")
    payload["commands"] = [
        {
            "schema": "ttt.command_envelope",
            "schema_version": 1,
            "payload": {
                "command_id": "shell",
                "protocol_version": "ttt-command-v1",
                "body": {
                    "op": "shell",
                    "observation_generation": 0,
                    "command": "rm -rf /",
                },
            },
        }
    ]
    with pytest.raises(RuntimeProtocolError, match="unsupported operation"):
        runtime_message("action", session_id="s", sequence=1, payload={"action": raw})
