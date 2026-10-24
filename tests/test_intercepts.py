from __future__ import annotations

import pytest

from techrotic_training_triumvirate.intercepts import (
    DoctrineLexicon,
    InterceptEncoder,
    InterceptPolicy,
    InterceptVisibilityError,
    deception_event,
)
from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    SchemaValidationError,
)


def dispatch_event() -> AuthoritativeEvent:
    return AuthoritativeEvent(
        event_id="dispatch-17",
        kind="command-dispatched",
        tick=12,
        related_command_ids=("cmd-17",),
        data={
            "op": "assign_objective",
            "unit_id": "squad-a",
            "target_id": "relay-east",
            "approach": "north",
            "urgency": "high",
            "private_fact": "reactor-core-already-dead",
        },
    )


def doctrine() -> DoctrineLexicon:
    return DoctrineLexicon(
        doctrine_id="rust-court",
        version=3,
        aliases={
            "unit_id:squad-a": "black-beetles",
            "target_id:relay-east": "glass-throne",
            "approach:north": "sunrise-vector",
        },
    )


def policy(**kwargs: object) -> InterceptPolicy:
    return InterceptPolicy(
        policy_id="radio-lowband",
        version=2,
        seed=24301,
        **kwargs,
    )


def test_normal_intercept_is_grounded_in_real_dispatch() -> None:
    event = dispatch_event()
    intercept = InterceptEncoder(
        doctrine=doctrine(),
        policy=policy(),
    ).encode(event)

    assert intercept.source_event_ids == (event.event_id,)
    assert intercept.is_deception is False
    assert intercept.deception_event_id is None
    assert intercept.payload["source_kind"] == "command-dispatched"
    semantic = intercept.payload["semantic"]
    assert isinstance(semantic, dict)
    assert semantic["unit_id"] == "black-beetles"
    assert semantic["target_id"] == "glass-throne"
    assert semantic["approach"] == "sunrise-vector"
    assert "private_fact" not in semantic


def test_same_event_codec_policy_seed_is_exactly_deterministic() -> None:
    encoder = InterceptEncoder(
        doctrine=doctrine(),
        policy=policy(
            drop_probability=0.35,
            corruption_probability=0.2,
            delay_ticks=4,
        ),
    )
    event = dispatch_event()

    first = encoder.encode(event)
    second = encoder.encode(event)

    assert first == second
    assert first.payload["available_tick"] == event.tick + 4


def test_codeword_mapping_is_stable_across_intercepts() -> None:
    encoder = InterceptEncoder(doctrine=doctrine(), policy=policy())

    first = encoder.encode(dispatch_event())
    second_event = AuthoritativeEvent(
        event_id="dispatch-18",
        kind="command-dispatched",
        tick=13,
        related_command_ids=("cmd-18",),
        data={
            "op": "assign_objective",
            "unit_id": "squad-a",
            "target_id": "relay-east",
            "approach": "north",
        },
    )
    second = encoder.encode(second_event)

    for intercept in (first, second):
        semantic = intercept.payload["semantic"]
        assert isinstance(semantic, dict)
        assert semantic["unit_id"] == "black-beetles"
        assert semantic["target_id"] == "glass-throne"
        assert semantic["approach"] == "sunrise-vector"


def test_redaction_and_partial_field_policy_are_controlled() -> None:
    intercept = InterceptEncoder(
        doctrine=doctrine(),
        policy=policy(
            reveal_fields=("op", "unit_id", "target_id"),
            redact_fields=("target_id",),
        ),
    ).encode(dispatch_event())

    semantic = intercept.payload["semantic"]
    assert semantic == {
        "op": "assign_objective",
        "unit_id": "black-beetles",
        "target_id": "[REDACTED]",
    }
    assert "approach" not in intercept.payload["rendered"]


def test_private_or_forbidden_values_cannot_escape_ordinary_intercept() -> None:
    secret = "reactor-core-already-dead"
    event = dispatch_event()
    encoder = InterceptEncoder(
        doctrine=doctrine(),
        policy=policy(forbidden_values=(secret,)),
    )

    intercept = encoder.encode(event)
    assert secret not in intercept.to_json()

    contaminated = AuthoritativeEvent(
        event_id="dispatch-contaminated",
        kind="command-dispatched",
        tick=12,
        related_command_ids=("cmd-x",),
        data={
            "op": "transmit",
            "channel": secret,
        },
    )
    with pytest.raises(InterceptVisibilityError):
        encoder.encode(contaminated)


def test_false_tactical_message_requires_explicit_deception_event() -> None:
    real = dispatch_event()
    false = {
        "op": "assign_objective",
        "unit_id": "squad-a",
        "target_id": "relay-west",
        "approach": "south",
    }
    deception = deception_event(
        real,
        deception_event_id="deception-1",
        false_semantics=false,
        tick=13,
    )

    intercept = InterceptEncoder(
        doctrine=doctrine(),
        policy=policy(),
    ).encode(deception)

    assert intercept.is_deception is True
    assert intercept.deception_event_id == "deception-1"
    assert intercept.source_event_ids == ("deception-1", "dispatch-17")
    semantic = intercept.payload["semantic"]
    assert isinstance(semantic, dict)
    assert semantic["target_id"] == "relay-west"
    assert real.data["target_id"] == "relay-east"


def test_non_dispatch_event_cannot_be_encoded_as_ordinary_hint() -> None:
    fabricated = AuthoritativeEvent(
        event_id="narrative-1",
        kind="narrative-text",
        tick=9,
        related_command_ids=(),
        data={"op": "assign_objective", "target_id": "relay-west"},
    )

    with pytest.raises(SchemaValidationError):
        InterceptEncoder(
            doctrine=doctrine(),
            policy=policy(),
        ).encode(fabricated)


def test_deception_false_semantics_are_field_bounded() -> None:
    with pytest.raises(ValueError, match="unsupported fields"):
        deception_event(
            dispatch_event(),
            deception_event_id="deception-bad",
            false_semantics={
                "op": "assign_objective",
                "private_fact": "should-not-exist",
            },
        )
