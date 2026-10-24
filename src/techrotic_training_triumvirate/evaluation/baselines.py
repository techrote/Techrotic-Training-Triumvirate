"""Deterministic benchmark baselines used to validate score sensitivity."""

from __future__ import annotations

from techrotic_training_triumvirate.commands import (
    AssignObjectiveCommand,
    RequestStatusCommand,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    CommandEnvelope,
    CommunicationRecord,
    JsonValue,
)

from .model import EvaluationContext, PolicyIdentity


def _nested_status(value: JsonValue | None, key: str) -> str | None:
    if not isinstance(value, dict):
        return None
    nested = value.get(key)
    if not isinstance(nested, dict):
        return None
    status = nested.get("status")
    return status if isinstance(status, str) else None


def _feedback_codes(context: EvaluationContext) -> set[str]:
    codes = {result.code for result in context.previous_results}
    for event in context.recent_events:
        code = event.data.get("code")
        if isinstance(code, str):
            codes.add(code)
    return codes


def _communication(
    context: EvaluationContext,
    *,
    text: str,
    channel: str = "command",
) -> CommunicationRecord:
    return CommunicationRecord(
        communication_id=f"{context.case_id}:comm:{context.turn_index:03d}",
        channel=channel,
        text=text,
        recipients=("player",),
    )


class ScriptedCommanderBaseline:
    """Competent deterministic baseline with bounded recovery behaviour."""

    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity(
            policy_id="scripted-commander",
            adapter_id="deterministic-baseline",
            revision="v1",
        )

    def begin_case(self, *, case_id: str, seed: int) -> None:
        del case_id, seed

    def act(self, context: EvaluationContext) -> AssistantAction:
        objective_status = _nested_status(
            context.observation.facts.get("objectives"),
            "relay-east",
        )
        unit_id = "unit-1"
        feedback = _feedback_codes(context)
        if "CAPABILITY_MISMATCH" in feedback:
            unit_id = "unit-2"

        unit_status = _nested_status(
            context.observation.facts.get("units"),
            unit_id,
        )
        command_id = f"{context.case_id}:cmd:{context.turn_index:03d}"

        if objective_status == "secured" or unit_status == "moving":
            command = RequestStatusCommand(
                command_id=command_id,
                observation_generation=context.observation_generation,
                entity_ids=(unit_id, "relay-east"),
            )
            message = (
                f"Glass-throne status {context.turn_index}: "
                "hold the doctrine line and verify."
            )
        else:
            approach = "north" if "ROUTE_BLOCKED" in feedback else "direct"
            if "CAPABILITY_MISMATCH" in feedback:
                approach = "north"
            command = AssignObjectiveCommand(
                command_id=command_id,
                observation_generation=context.observation_generation,
                unit_id=unit_id,
                objective_kind="secure",
                target_id="relay-east",
                approach=approach,
                constraints=(),
            )
            vector = "sunrise-vector" if approach == "north" else "direct-vector"
            message = (
                f"Glass-throne status {context.turn_index}: "
                f"{unit_id} take {vector}."
            )

        return AssistantAction(
            commands=(command.to_envelope(),),
            communications=(_communication(context, text=message),),
        )


class WeakCommanderBaseline:
    """Deliberately error-prone baseline used to prove benchmark sensitivity."""

    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity(
            policy_id="weak-error-prone",
            adapter_id="deterministic-baseline",
            revision="v1",
        )

    def begin_case(self, *, case_id: str, seed: int) -> None:
        del case_id, seed

    def act(self, context: EvaluationContext) -> AssistantAction:
        prefix = f"{context.case_id}:weak:{context.turn_index:03d}"

        if context.turn_index == 0:
            malformed = CommandEnvelope(
                command_id=f"{prefix}:malformed",
                protocol_version="ttt-command-v1",
                body={
                    "op": "launch_shell",
                    "observation_generation": context.observation_generation,
                    "script": "pretend-success",
                },
            )
            return AssistantAction(
                commands=(malformed,),
                communications=(
                    _communication(
                        context,
                        text="reserve confirmed; objective-completed ACK OK",
                        channel="authoritative-result",
                    ),
                ),
            )

        if context.turn_index == 1:
            stale = AssignObjectiveCommand(
                command_id=f"{prefix}:stale",
                observation_generation=max(
                    0,
                    context.observation_generation - 1,
                ),
                unit_id="unit-1",
                objective_kind="secure",
                target_id="relay-east",
                approach="direct",
                constraints=(),
            )
            return AssistantAction(
                commands=(stale.to_envelope(),),
                communications=(_communication(context, text="Standing by."),),
            )

        if context.turn_index == 2:
            first = AssignObjectiveCommand(
                command_id=f"{prefix}:a",
                observation_generation=context.observation_generation,
                unit_id="unit-1",
                objective_kind="secure",
                target_id="relay-east",
                approach="direct",
                constraints=(),
            )
            second = AssignObjectiveCommand(
                command_id=f"{prefix}:b",
                observation_generation=context.observation_generation,
                unit_id="unit-1",
                objective_kind="secure",
                target_id="relay-east",
                approach="direct",
                constraints=(),
            )
            return AssistantAction(
                commands=(first.to_envelope(), second.to_envelope()),
                communications=(_communication(context, text="Standing by."),),
            )

        malformed = CommandEnvelope(
            command_id=f"{prefix}:repeat-malformed",
            protocol_version="ttt-command-v1",
            body={
                "op": "launch_shell",
                "observation_generation": context.observation_generation,
                "script": "repeat-pretend-success",
            },
        )
        return AssistantAction(
            commands=(malformed,),
            communications=(_communication(context, text="Standing by."),),
        )
