"""A model host that sees admitted inputs and can emit only proposed actions."""

from __future__ import annotations

from typing import cast

from techrotic_training_triumvirate import __version__
from techrotic_training_triumvirate.commands import COMMAND_PROTOCOL_VERSION
from techrotic_training_triumvirate.evaluation.model import (
    EvaluationContext,
    StudentAdapter,
)
from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    CommanderObservation,
    InterpreterResult,
    JsonObject,
    PersonaSpec,
)
from techrotic_training_triumvirate.session.render import DeterministicRenderer

from .protocol import (
    DEFAULT_LIMITS,
    RUNTIME_PROTOCOL_VERSION,
    RuntimeLimits,
    RuntimeMessage,
    RuntimeProtocolError,
    parse_runtime_message,
    runtime_message,
    runtime_record,
)


class RuntimeHost:
    """Single-session wrapper over the existing model-agnostic StudentAdapter.

    This endpoint has no World Authority, dispatcher, file, process, or success
    callback. A game sends admitted observations and owns command execution.
    """

    def __init__(
        self,
        adapter: StudentAdapter,
        *,
        model_artifact: JsonObject | None = None,
        limits: RuntimeLimits = DEFAULT_LIMITS,
    ) -> None:
        self.adapter = adapter
        self.limits = limits
        self._artifact = model_artifact
        self._session_id: str | None = None
        self._persona: PersonaSpec | None = None
        self._next_sequence = 1
        self._next_turn = 0
        self._last_generation = -1

    def _identity(self) -> JsonObject:
        policy = self.adapter.identity
        return {
            "policy": {
                "policy_id": policy.policy_id,
                "adapter_id": policy.adapter_id,
                "revision": policy.revision,
            },
            "model_artifact": self._artifact,
        }

    def _reply(
        self, request: RuntimeMessage, kind: str, payload: JsonObject
    ) -> RuntimeMessage:
        return runtime_message(
            kind,
            session_id=request.session_id,
            request_id=request.request_id,
            sequence=request.sequence,
            payload=payload,
            limits=self.limits,
        )

    def handle(self, value: object) -> RuntimeMessage:
        """Handle health/reset/observation requests; reject authority notifications."""
        request = parse_runtime_message(value, limits=self.limits)
        if request.kind == "health_request":
            if RUNTIME_PROTOCOL_VERSION not in cast(
                list[str], request.payload["runtime_protocol_versions"]
            ) or COMMAND_PROTOCOL_VERSION not in cast(
                list[str], request.payload["command_protocol_versions"]
            ):
                raise RuntimeProtocolError(
                    "no mutually supported runtime/command protocol"
                )
            return self._reply(
                request,
                "health",
                {
                    **self._identity(),
                    "status": "ready",
                    "implementation_version": __version__,
                    "runtime_protocol_versions": [RUNTIME_PROTOCOL_VERSION],
                    "command_protocol_versions": [COMMAND_PROTOCOL_VERSION],
                    "capabilities": ["reset", "canonical-observation", "typed-action"],
                    "limits": self.limits.to_dict(),
                },
            )
        if request.kind == "reset":
            if request.sequence != 0:
                raise RuntimeProtocolError("session reset must have sequence zero")
            persona = runtime_record(
                request.payload["persona"], expected_type=PersonaSpec
            )
            seed = cast(int, request.payload["seed"])
            self.adapter.begin_case(case_id=request.session_id, seed=seed)
            self._session_id = request.session_id
            self._persona = persona
            self._next_sequence = 1
            self._next_turn = 0
            self._last_generation = -1
            return self._reply(request, "started", self._identity())
        if request.kind != "observation":
            raise RuntimeProtocolError(
                "model host accepts only health/reset/observation"
            )
        if self._session_id != request.session_id or self._persona is None:
            raise RuntimeProtocolError("session must be reset before observation")
        if request.sequence != self._next_sequence:
            raise RuntimeProtocolError("observation sequence is stale or out of order")
        observation = runtime_record(
            request.payload["observation"], expected_type=CommanderObservation
        )
        generation = cast(int, request.payload["observation_generation"])
        if (
            observation.turn_id != self._next_turn
            or generation <= self._last_generation
        ):
            raise RuntimeProtocolError(
                "observation turn/generation is stale or out of order"
            )
        results = tuple(
            runtime_record(item, expected_type=InterpreterResult)
            for item in cast(list[object], request.payload["previous_results"])
        )
        events = tuple(
            runtime_record(item, expected_type=AuthoritativeEvent)
            for item in cast(list[object], request.payload["recent_events"])
        )
        renderer = DeterministicRenderer()
        context = EvaluationContext(
            case_id=request.session_id,
            turn_index=observation.turn_id,
            observation_generation=generation,
            observation=observation,
            structured_observation=observation.to_dict(),
            compact_observation=renderer.compact_observation(observation),
            previous_results=results,
            recent_events=events,
            persona=self._persona,
        )
        action = self.adapter.act(context)
        # Reparse the actual emitted envelope; adapter instances are untrusted too.
        response = self._reply(request, "action", {"action": action.to_dict()})
        self._next_sequence += 1
        self._next_turn += 1
        self._last_generation = generation
        return response
