from __future__ import annotations

import json

import pytest

from techrotic_training_triumvirate.schemas import (
    PlayerInterceptEnvelope,
    SchemaValidationError,
    UnknownSchemaError,
    UnsupportedSchemaVersionError,
    load_record,
)
from techrotic_training_triumvirate.schemas.fixtures import (
    EVALUATOR_SENTINEL,
    PRIVATE_SENTINEL,
    t0_hidden_information_turn,
    t0_normal_turn,
)


def test_unknown_schema_version_refuses() -> None:
    envelope = t0_normal_turn().to_dict()
    envelope["schema_version"] = 999

    with pytest.raises(
        UnsupportedSchemaVersionError,
        match="version 999 is unsupported",
    ):
        load_record(envelope)


def test_unknown_schema_name_refuses() -> None:
    envelope = t0_normal_turn().to_dict()
    envelope["schema"] = "ttt.future_unknown"

    with pytest.raises(UnknownSchemaError, match="unknown schema"):
        load_record(envelope)


def test_unknown_payload_field_refuses() -> None:
    envelope = t0_normal_turn().observation.to_dict()
    payload = envelope["payload"]
    assert isinstance(payload, dict)
    payload["future_field"] = "must-not-be-silently-ignored"

    with pytest.raises(SchemaValidationError, match="unknown fields"):
        load_record(envelope)


def test_hidden_and_evaluator_only_values_do_not_leak_to_observation_views() -> None:
    turn = t0_hidden_information_turn()

    assert PRIVATE_SENTINEL in turn.commander_private_context.to_json()
    assert EVALUATOR_SENTINEL in turn.annotations.to_json()

    commander_observation = turn.observation.to_json()
    player_observation = turn.player_observation.to_json()
    player_intercepts = json.dumps(
        [intercept.to_dict() for intercept in turn.player_intercepts],
        sort_keys=True,
    )

    for public_view in (
        commander_observation,
        player_observation,
        player_intercepts,
    ):
        assert PRIVATE_SENTINEL not in public_view
        assert EVALUATOR_SENTINEL not in public_view

    assert "secret-reactor-state" not in player_observation
    assert "secret-reactor-state" not in player_intercepts


def test_intercept_deception_requires_explicit_deception_event() -> None:
    envelope = PlayerInterceptEnvelope(
        intercept_id="intercept-test",
        source_event_ids=("event-1",),
        payload={"message": "false western attack"},
        is_deception=True,
        deception_event_id="event-deception-1",
    )
    assert load_record(envelope.to_dict()) == envelope

    invalid = envelope.to_dict()
    payload = invalid["payload"]
    assert isinstance(payload, dict)
    payload["deception_event_id"] = None

    with pytest.raises(
        SchemaValidationError,
        match="deception_event_id is required",
    ):
        load_record(invalid)
