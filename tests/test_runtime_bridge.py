"""Deterministic full JSON runtime sessions and grounded intercept evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from techrotic_training_triumvirate.evaluation.baselines import (
    ScriptedCommanderBaseline,
)
from techrotic_training_triumvirate.evaluation.model import (
    EvaluationContext,
    PolicyIdentity,
)
from techrotic_training_triumvirate.intercepts import (
    DoctrineLexicon,
    InterceptEncoder,
    InterceptPolicy,
    deception_event,
)
from techrotic_training_triumvirate.recovery import ScriptedStep, ScriptedStudentAdapter
from techrotic_training_triumvirate.runtime import (
    GameStep,
    InProcessTransport,
    NativeGameAdapter,
    ReferenceRuntimeBridge,
    RuntimeHost,
    RuntimeProtocolError,
    commander_events,
    default_runtime_persona,
    parse_runtime_message,
    run_runtime_demo,
    runtime_message,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    InterpreterResult,
    PlayerInterceptEnvelope,
    canonical_json,
    load_record,
)


def _encoder(*, delay: int = 0) -> InterceptEncoder:
    return InterceptEncoder(
        doctrine=DoctrineLexicon("runtime-test", 1, {"unit_id:unit-1": "beetles"}),
        policy=InterceptPolicy("runtime-test", delay_ticks=delay, seed=24301),
    )


def _bridge(
    *,
    host: RuntimeHost | None = None,
    game: NativeGameAdapter | None = None,
    delay: int = 0,
) -> ReferenceRuntimeBridge:
    bridge = ReferenceRuntimeBridge(
        InProcessTransport(host or RuntimeHost(ScriptedCommanderBaseline())),
        game or NativeGameAdapter(),
        encoder=_encoder(delay=delay),
    )
    bridge.start(
        session_id="test-session", seed=24301, persona=default_runtime_persona()
    )
    return bridge


def test_demo_is_reproducible_and_intercepts_reference_real_dispatch() -> None:
    first = run_runtime_demo(seed=24301, turns=8)
    assert first == run_runtime_demo(seed=24301, turns=8)
    assert first != run_runtime_demo(seed=24302, turns=8)
    bridge = _bridge()
    for _ in range(8):
        turn = bridge.step()
        dispatch_ids = {
            load_record(
                message.payload["event"], expected_type=AuthoritativeEvent
            ).event_id
            for message in turn.dispatches
        }
        for message in turn.intercepts:
            intercept = load_record(
                message.payload["intercept"], expected_type=PlayerInterceptEnvelope
            )
            assert len(intercept.source_event_ids) == 1
            assert set(intercept.source_event_ids) <= dispatch_ids
            assert not intercept.is_deception


def test_world_validates_unknown_unit_and_stale_generation_without_dispatch() -> None:
    adapter = ScriptedStudentAdapter(
        identity=PolicyIdentity("bad", "script", "v1"),
        steps=(
            ScriptedStep(command_body={"op": "hold", "unit_id": "missing"}),
            ScriptedStep(
                command_body={"op": "hold", "unit_id": "unit-1"}, generation_offset=-1
            ),
        ),
    )
    bridge = _bridge(host=RuntimeHost(adapter))
    for code in ("ENTITY_UNKNOWN", "STALE_OBSERVATION"):
        turn = bridge.step()
        assert turn.dispatches == turn.intercepts == ()
        results = turn.feedback.payload["results"]
        assert isinstance(results, list)
        result = load_record(results[0], expected_type=InterpreterResult)
        assert not result.accepted
        assert result.code == code


def test_model_receives_authoritative_feedback_and_observed_state_only() -> None:
    class Capture(ScriptedCommanderBaseline):
        contexts: list[EvaluationContext] = []

        def act(self, context: EvaluationContext) -> AssistantAction:
            self.contexts.append(context)
            return super().act(context)

    adapter = Capture()
    game = NativeGameAdapter()
    bridge = _bridge(host=RuntimeHost(adapter), game=game)
    first = bridge.step()
    bridge.step()
    second = adapter.contexts[-1]
    assert second.previous_results[0].accepted
    assert second.recent_events
    assert second.observation.turn_id == 1
    assert second.observation_generation == 1
    serialized = canonical_json(
        {
            "observations": [
                context.observation.to_dict() for context in adapter.contexts
            ],
            "feedback": first.feedback.to_dict(),
        }
    )
    for secret in game.world.blueprint.private_facts.values():
        if isinstance(secret, str):
            assert secret not in serialized
    private_event = AuthoritativeEvent(
        "private", "private-debug", 0, (), {"secret": "sentinel"}
    )
    assert commander_events((private_event,)) == ()
    event = AuthoritativeEvent(
        "safe", "command-dispatched", 0, (), {"op": "hold", "private_debug": "sentinel"}
    )
    assert "sentinel" not in canonical_json(
        [item.to_dict() for item in commander_events((event,))]
    )


def test_acceptance_is_distinct_from_world_execution_failure() -> None:
    bridge = _bridge()
    turn = bridge.step()
    results = turn.feedback.payload["results"]
    events = turn.feedback.payload["events"]
    assert isinstance(results, list) and isinstance(events, list)
    assert load_record(results[0], expected_type=InterpreterResult).accepted
    assert any(
        load_record(event, expected_type=AuthoritativeEvent).kind == "execution-failed"
        for event in events
    )
    assert turn.intercepts


def test_delayed_intercept_delivery_does_not_invent_new_dispatch() -> None:
    bridge = _bridge(delay=3)
    first = bridge.step()
    assert first.intercepts == ()
    assert bridge.step().intercepts == ()
    delivered = bridge.step().intercepts
    assert delivered
    original = load_record(
        first.dispatches[0].payload["event"], expected_type=AuthoritativeEvent
    )
    intercept = load_record(
        delivered[0].payload["intercept"], expected_type=PlayerInterceptEnvelope
    )
    assert intercept.source_event_ids == (original.event_id,)
    assert intercept.payload["available_tick"] == 3


def test_player_notification_does_not_bypass_intercept_redaction() -> None:
    game = NativeGameAdapter()
    encoder = InterceptEncoder(
        doctrine=DoctrineLexicon("redacted", 1, {}),
        policy=InterceptPolicy("redacted", reveal_fields=("op",)),
    )
    bridge = ReferenceRuntimeBridge(
        InProcessTransport(RuntimeHost(ScriptedCommanderBaseline())),
        game,
        encoder=encoder,
    )
    bridge.start(session_id="redacted", seed=24301, persona=default_runtime_persona())
    turn = bridge.step()
    assert turn.dispatches
    wire = turn.intercepts[0].to_json()
    assert '"source_events"' not in wire
    assert "unit-1" not in wire
    assert "relay-east" not in wire
    intercept = load_record(
        turn.intercepts[0].payload["intercept"], expected_type=PlayerInterceptEnvelope
    )
    assert intercept.payload["semantic"] == {"op": "assign_objective"}


def test_runtime_deception_keeps_both_authoritative_sources() -> None:
    class DeceptiveGame(NativeGameAdapter):
        def execute(self, action: AssistantAction) -> GameStep:
            result = super().execute(action)
            dispatch = next(
                event for event in result.events if event.kind == "command-dispatched"
            )
            deception = deception_event(
                dispatch,
                deception_event_id="false-broadcast",
                false_semantics={"op": "hold", "unit_id": "unit-2"},
            )
            self.world.events.append(deception)
            return GameStep(result.results, result.events + (deception,))

    turn = _bridge(game=DeceptiveGame()).step()
    assert len(turn.intercepts) == 2
    ordinary = load_record(
        turn.intercepts[0].payload["intercept"], expected_type=PlayerInterceptEnvelope
    )
    deception = load_record(
        turn.intercepts[1].payload["intercept"], expected_type=PlayerInterceptEnvelope
    )
    assert deception.is_deception
    assert deception.deception_event_id == "false-broadcast"
    assert deception.source_event_ids == (
        "false-broadcast",
        ordinary.source_event_ids[0],
    )
    raw = turn.intercepts[1].to_dict()
    forged = replace(deception, source_event_ids=())
    raw["payload"] = {"intercept": forged.to_dict()}
    with pytest.raises(RuntimeProtocolError, match="source"):
        parse_runtime_message(raw)


def test_host_refuses_replay_turn_order_and_bridge_reset_reproduces_world() -> None:
    host = RuntimeHost(ScriptedCommanderBaseline())
    bridge = _bridge(host=host)
    first = bridge.step()
    with pytest.raises(RuntimeProtocolError, match="sequence"):
        host.handle(first.observation)
    bridge.start(
        session_id="test-session", seed=24301, persona=default_runtime_persona()
    )
    assert bridge.step() == first


def test_bridge_checks_host_response_before_any_world_mutation() -> None:
    class Tamper(InProcessTransport):
        def exchange(self, message: str) -> str:
            response = super().exchange(message)
            parsed = parse_runtime_message(response)
            if parsed.kind == "action":
                return replace(parsed, request_id="wrong-request").to_json()
            return response

    game = NativeGameAdapter()
    bridge = ReferenceRuntimeBridge(
        Tamper(RuntimeHost(ScriptedCommanderBaseline())), game, encoder=_encoder()
    )
    bridge.start(
        session_id="test-session", seed=24301, persona=default_runtime_persona()
    )
    before = game.world.state_hash()
    with pytest.raises(RuntimeProtocolError, match="correlation"):
        bridge.step()
    assert game.world.state_hash() == before
    assert game.world.events == []


def test_duplicate_model_command_identity_is_not_dispatched_twice() -> None:
    class ReusedID(ScriptedCommanderBaseline):
        def act(self, context: EvaluationContext) -> AssistantAction:
            action = super().act(context)
            return AssistantAction(
                tuple(
                    replace(command, command_id="constant")
                    for command in action.commands
                ),
                (),
            )

    game = NativeGameAdapter()
    bridge = _bridge(host=RuntimeHost(ReusedID()), game=game)
    bridge.step()
    before = game.world.state_hash()
    with pytest.raises(RuntimeProtocolError, match="replayed command"):
        bridge.step()
    assert game.world.state_hash() == before


def test_action_command_count_is_bounded_before_execution() -> None:
    first = _bridge().step()
    raw = load_record(first.action.payload["action"], expected_type=AssistantAction)
    too_many = AssistantAction(
        tuple(replace(raw.commands[0], command_id=f"c-{i}") for i in range(9)), ()
    )
    with pytest.raises(RuntimeProtocolError, match="too many commands"):
        runtime_message(
            "action", session_id="s", sequence=1, payload={"action": too_many.to_dict()}
        )
