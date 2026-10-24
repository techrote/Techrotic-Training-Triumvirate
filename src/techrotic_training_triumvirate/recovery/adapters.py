"""Deterministic StudentAdapter implementations for corrective-rollout tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from techrotic_training_triumvirate.evaluation.model import (
    EvaluationContext,
    PolicyIdentity,
    StudentAdapter,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    CommandEnvelope,
    CommunicationRecord,
)

from .model import ScriptedStep


class ScriptedStudentAdapter:
    """Deterministic command-body script with observation-generation binding."""

    def __init__(
        self,
        *,
        identity: PolicyIdentity,
        steps: tuple[ScriptedStep, ...],
        repeat_last: bool = True,
    ) -> None:
        if not steps:
            raise ValueError("script must contain at least one step")
        self._identity = identity
        self._steps = steps
        self._repeat_last = repeat_last

    @property
    def identity(self) -> PolicyIdentity:
        return self._identity

    def begin_case(self, *, case_id: str, seed: int) -> None:
        del case_id, seed

    def act(self, context: EvaluationContext) -> AssistantAction:
        if context.turn_index >= len(self._steps) and not self._repeat_last:
            return AssistantAction(commands=(), communications=())
        index = min(context.turn_index, len(self._steps) - 1)
        step = self._steps[index]
        generation = max(
            0,
            context.observation_generation + step.generation_offset,
        )
        body = dict(step.command_body)
        body["observation_generation"] = generation
        envelope = CommandEnvelope(
            command_id=(
                f"{self.identity.policy_id}:{context.case_id}:{context.turn_index:03d}"
            ),
            protocol_version="ttt-command-v1",
            body=body,
        )
        communications: tuple[CommunicationRecord, ...] = ()
        if step.communication_text is not None:
            communications = (
                CommunicationRecord(
                    communication_id=(
                        f"{self.identity.policy_id}:{context.case_id}:"
                        f"comm:{context.turn_index:03d}"
                    ),
                    channel=step.communication_channel,
                    text=step.communication_text,
                    recipients=("player",),
                ),
            )
        return AssistantAction(
            commands=(envelope,),
            communications=communications,
        )


class ReplayCorrectionAdapter:
    """Replay admitted corrections at the exact student-visible state hash."""

    def __init__(
        self,
        *,
        corrections: Mapping[str, AssistantAction],
        fallback: StudentAdapter,
        revision: str,
    ) -> None:
        if not revision.strip():
            raise ValueError("revision must not be empty")
        self._corrections = dict(corrections)
        self._fallback = fallback
        self._identity = PolicyIdentity(
            policy_id="replayed-corrections",
            adapter_id="ttt-010-replay",
            revision=revision,
        )

    @classmethod
    def from_pairs(
        cls,
        pairs: Iterable[tuple[str, AssistantAction]],
        *,
        fallback: StudentAdapter,
        revision: str,
    ) -> ReplayCorrectionAdapter:
        selected: dict[str, AssistantAction] = {}
        for observation_hash, action in pairs:
            selected.setdefault(observation_hash, action)
        return cls(
            corrections=selected,
            fallback=fallback,
            revision=revision,
        )

    @property
    def identity(self) -> PolicyIdentity:
        return self._identity

    def begin_case(self, *, case_id: str, seed: int) -> None:
        self._fallback.begin_case(case_id=case_id, seed=seed)

    def act(self, context: EvaluationContext) -> AssistantAction:
        action = self._corrections.get(context.observation.content_hash())
        if action is None:
            return self._fallback.act(context)

        commands = tuple(
            CommandEnvelope(
                command_id=(
                    f"{context.case_id}:replay:{context.turn_index:03d}:{index:02d}"
                ),
                protocol_version=envelope.protocol_version,
                body={
                    **envelope.body,
                    "observation_generation": context.observation_generation,
                },
            )
            for index, envelope in enumerate(action.commands)
        )
        communications = tuple(
            CommunicationRecord(
                communication_id=(
                    f"{context.case_id}:replay-comm:"
                    f"{context.turn_index:03d}:{index:02d}"
                ),
                channel=communication.channel,
                text=communication.text,
                recipients=communication.recipients,
            )
            for index, communication in enumerate(action.communications)
        )
        return AssistantAction(
            commands=commands,
            communications=communications,
        )
