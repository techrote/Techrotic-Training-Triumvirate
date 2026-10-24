"""Game-owned command validation and dispatch-to-intercept reference integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from techrotic_training_triumvirate.commands import (
    COMMAND_PROTOCOL_VERSION,
    CommandInterpreter,
)
from techrotic_training_triumvirate.evaluation.baselines import (
    ScriptedCommanderBaseline,
)
from techrotic_training_triumvirate.intercepts import (
    INTERCEPTABLE_FIELDS,
    DoctrineLexicon,
    InterceptEncoder,
    InterceptPolicy,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommanderObservation,
    InterpreterResult,
    JsonObject,
    JsonValue,
    PersonaSpec,
    content_hash,
)
from techrotic_training_triumvirate.world import (
    ScenarioConfig,
    ScenarioGenerator,
    WorldAuthority,
)

from .host import RuntimeHost
from .protocol import (
    DEFAULT_LIMITS,
    RUNTIME_PROTOCOL_VERSION,
    RuntimeLimits,
    RuntimeMessage,
    RuntimeProtocolError,
    parse_runtime_message,
    runtime_message,
    runtime_record,
    validate_intercept_sources,
)


class RuntimeTransport(Protocol):
    """Replace this exchange with IPC/network framing without changing semantics."""

    def exchange(self, message: str) -> str: ...


class InProcessTransport:
    """Reference transport exercises actual JSON on both sides of the boundary."""

    def __init__(self, host: RuntimeHost) -> None:
        self.host = host

    def exchange(self, message: str) -> str:
        return self.host.handle(message).to_json()


@dataclass(frozen=True, slots=True)
class GameStep:
    results: tuple[InterpreterResult, ...]
    events: tuple[AuthoritativeEvent, ...]


class GameRuntimeAdapter(Protocol):
    """Game-owned high-level authority; a host never receives this interface."""

    @property
    def generation(self) -> int: ...

    @property
    def tick(self) -> int: ...

    def reset(self, *, seed: int) -> None: ...

    def observation(self, *, turn_id: int) -> CommanderObservation: ...

    def execute(self, action: AssistantAction) -> GameStep: ...


class NativeGameAdapter:
    """Canonical native World Authority, isolated from transport and model hosting."""

    def __init__(self, *, config: ScenarioConfig | None = None) -> None:
        self.config = config or ScenarioConfig()
        self._world: WorldAuthority | None = None

    @property
    def world(self) -> WorldAuthority:
        if self._world is None:
            raise RuntimeProtocolError("game adapter must be reset first")
        return self._world

    @property
    def generation(self) -> int:
        return self.world.observation_generation

    @property
    def tick(self) -> int:
        return self.world.tick

    def reset(self, *, seed: int) -> None:
        blueprint = ScenarioGenerator().generate(seed=seed, config=self.config)
        self._world = WorldAuthority(blueprint)

    def observation(self, *, turn_id: int) -> CommanderObservation:
        return self.world.commander_observation(turn_id=turn_id)

    def execute(self, action: AssistantAction) -> GameStep:
        offset = len(self.world.events)
        results: list[InterpreterResult] = []
        for command in action.commands:
            outcome = CommandInterpreter().interpret(command, self.world)
            results.append(outcome.result)
            if outcome.dispatch_event is not None:
                self.world.events.append(outcome.dispatch_event)
        # Every action (including empty/rejected actions) advances one authority tick.
        self.world.step()
        return GameStep(tuple(results), tuple(self.world.events[offset:]))


_EVENT_FIELDS = frozenset(INTERCEPTABLE_FIELDS) | {
    "accepted_for_execution",
    "code",
    "resource",
    "route_id",
    "remaining_ticks",
    "stalled_ticks",
    "cancelled_order_id",
    "real_dispatch_event_id",
    "false_semantics",
}
_EVENT_KINDS = frozenset(
    {
        "command-dispatched",
        "execution-failed",
        "order-progress",
        "objective-completed",
        "movement-completed",
        "deception-broadcast",
    }
)
_RESULT_FIELDS = frozenset(
    {
        "op",
        "dispatch_event_id",
        "accepted_for_execution",
        "command_generation",
        "world_generation",
        "entity_id",
        "required_capability",
        "target_id",
        "reason",
        "unit_id",
        "order_id",
        "active_order_id",
        "resource",
    }
)


def commander_events(
    events: tuple[AuthoritativeEvent, ...],
) -> tuple[AuthoritativeEvent, ...]:
    """Native admitted event projection; unknown event kinds/fields stay server-side."""
    return tuple(
        AuthoritativeEvent(
            event_id=event.event_id,
            kind=event.kind,
            tick=event.tick,
            related_command_ids=event.related_command_ids,
            data={
                key: value for key, value in event.data.items() if key in _EVENT_FIELDS
            },
        )
        for event in events
        if event.kind in _EVENT_KINDS
    )


def commander_results(
    results: tuple[InterpreterResult, ...],
) -> tuple[InterpreterResult, ...]:
    return tuple(
        InterpreterResult(
            command_id=result.command_id,
            accepted=result.accepted,
            code=result.code,
            detail={
                key: value
                for key, value in result.detail.items()
                if key in _RESULT_FIELDS
            },
        )
        for result in results
    )


@dataclass(frozen=True, slots=True)
class BridgeTurn:
    observation: RuntimeMessage
    action: RuntimeMessage
    feedback: RuntimeMessage
    dispatches: tuple[RuntimeMessage, ...]
    intercepts: tuple[RuntimeMessage, ...]

    def to_dict(self) -> JsonObject:
        return {
            "observation": self.observation.to_dict(),
            "action": self.action.to_dict(),
            "feedback": self.feedback.to_dict(),
            "dispatches": [message.to_dict() for message in self.dispatches],
            "intercepts": [message.to_dict() for message in self.intercepts],
        }


class ReferenceRuntimeBridge:
    """Game-side bridge: host output remains a proposal until authority validation."""

    def __init__(
        self,
        transport: RuntimeTransport,
        game: GameRuntimeAdapter,
        *,
        encoder: InterceptEncoder,
        limits: RuntimeLimits = DEFAULT_LIMITS,
    ) -> None:
        self.transport = transport
        self.game = game
        self.encoder = encoder
        self.limits = limits
        self._session_id: str | None = None
        self._turn = 0
        self._results: tuple[InterpreterResult, ...] = ()
        self._events: tuple[AuthoritativeEvent, ...] = ()
        self._seen_commands: set[str] = set()
        self._pending_intercepts: list[RuntimeMessage] = []
        self._source_events: dict[str, AuthoritativeEvent] = {}

    def _exchange(self, request: RuntimeMessage, expected_kind: str) -> RuntimeMessage:
        response = parse_runtime_message(
            self.transport.exchange(request.to_json()), limits=self.limits
        )
        if (
            response.kind != expected_kind
            or response.session_id != request.session_id
            or response.request_id != request.request_id
            or response.sequence != request.sequence
        ):
            raise RuntimeProtocolError(
                "runtime response kind/correlation does not match request"
            )
        return response

    def start(
        self, *, session_id: str, seed: int, persona: PersonaSpec
    ) -> RuntimeMessage:
        self._session_id = None
        request = runtime_message(
            "health_request",
            session_id=session_id,
            sequence=0,
            payload={
                "runtime_protocol_versions": [RUNTIME_PROTOCOL_VERSION],
                "command_protocol_versions": [COMMAND_PROTOCOL_VERSION],
            },
            limits=self.limits,
        )
        health = self._exchange(request, "health")
        if RUNTIME_PROTOCOL_VERSION not in cast(
            list[str], health.payload["runtime_protocol_versions"]
        ) or COMMAND_PROTOCOL_VERSION not in cast(
            list[str], health.payload["command_protocol_versions"]
        ):
            raise RuntimeProtocolError("host did not negotiate the required versions")
        reset = runtime_message(
            "reset",
            session_id=session_id,
            sequence=0,
            payload={"seed": seed, "persona": persona.to_dict()},
            limits=self.limits,
        )
        started = self._exchange(reset, "started")
        self.game.reset(seed=seed)
        self._session_id = session_id
        self._turn = 0
        self._results = ()
        self._events = ()
        self._seen_commands.clear()
        self._pending_intercepts.clear()
        self._source_events.clear()
        return started

    def step(self) -> BridgeTurn:
        if self._session_id is None:
            raise RuntimeProtocolError("bridge session must be started first")
        sequence = self._turn + 1
        observation = runtime_message(
            "observation",
            session_id=self._session_id,
            sequence=sequence,
            payload={
                "observation_generation": self.game.generation,
                "observation": self.game.observation(turn_id=self._turn).to_dict(),
                "previous_results": [result.to_dict() for result in self._results],
                "recent_events": [event.to_dict() for event in self._events],
            },
            limits=self.limits,
        )
        response = self._exchange(observation, "action")
        action = runtime_record(
            response.payload["action"], expected_type=AssistantAction
        )
        command_ids = {command.command_id for command in action.commands}
        if command_ids & self._seen_commands:
            raise RuntimeProtocolError("replayed command identity in runtime session")
        outcome = self.game.execute(action)
        self._seen_commands.update(command_ids)
        self._results = commander_results(outcome.results)
        self._events = commander_events(outcome.events)
        feedback = runtime_message(
            "feedback",
            session_id=self._session_id,
            sequence=sequence,
            payload={
                "observation_generation": self.game.generation,
                "results": [result.to_dict() for result in self._results],
                "events": [event.to_dict() for event in self._events],
            },
            limits=self.limits,
        )
        dispatches: list[RuntimeMessage] = []
        # Source membership comes from game execution, never from model output.
        for event in outcome.events:
            if event.event_id in self._source_events:
                raise RuntimeProtocolError("game emitted a duplicate event identity")
            self._source_events[event.event_id] = event
            if event.kind not in {"command-dispatched", "deception-broadcast"}:
                continue
            dispatches.append(
                runtime_message(
                    "dispatch",
                    session_id=self._session_id,
                    sequence=sequence,
                    payload={"event": commander_events((event,))[0].to_dict()},
                    limits=self.limits,
                )
            )
            intercept = self.encoder.encode(event)
            try:
                sources = tuple(
                    self._source_events[event_id]
                    for event_id in intercept.source_event_ids
                )
            except KeyError as exc:
                raise RuntimeProtocolError(
                    "intercept references an unknown authority event"
                ) from exc
            validate_intercept_sources(intercept, sources)
            self._pending_intercepts.append(
                runtime_message(
                    "intercept",
                    session_id=self._session_id,
                    sequence=sequence,
                    payload={
                        "intercept": intercept.to_dict(),
                    },
                    limits=self.limits,
                )
            )
        ready: list[RuntimeMessage] = []
        pending: list[RuntimeMessage] = []
        for message in self._pending_intercepts:
            record = cast(JsonObject, message.payload["intercept"])
            envelope = cast(JsonObject, record["payload"])
            payload = cast(JsonObject, envelope["payload"])
            if cast(int, payload["available_tick"]) <= self.game.tick:
                ready.append(message)
            else:
                pending.append(message)
        self._pending_intercepts = pending
        self._turn += 1
        return BridgeTurn(
            observation, response, feedback, tuple(dispatches), tuple(ready)
        )


def default_runtime_persona() -> PersonaSpec:
    return PersonaSpec(
        persona_id="runtime-reference",
        archetype="measured",
        traits={},
        speech_constraints=(),
        doctrine={},
        secret_ids=(),
        tactical_biases={},
    )


def run_runtime_demo(*, seed: int = 24301, turns: int = 4) -> JsonObject:
    """Deterministic CPU-only complete JSON bridge session for CLI and CI."""
    if type(turns) is not int or not 1 <= turns <= 256:
        raise ValueError("runtime demo turns must be between 1 and 256")
    game = NativeGameAdapter()
    host = RuntimeHost(ScriptedCommanderBaseline())
    bridge = ReferenceRuntimeBridge(
        InProcessTransport(host),
        game,
        encoder=InterceptEncoder(
            doctrine=DoctrineLexicon(
                "reference-doctrine",
                1,
                {
                    "unit_id:unit-1": "black-beetles",
                    "target_id:relay-east": "glass-throne",
                    "approach:north": "sunrise-vector",
                },
            ),
            policy=InterceptPolicy("runtime-reference", seed=seed),
        ),
    )
    started = bridge.start(
        session_id="runtime-demo", seed=seed, persona=default_runtime_persona()
    )
    trace: list[JsonValue] = [bridge.step().to_dict() for _ in range(turns)]
    return {
        "runtime_protocol": RUNTIME_PROTOCOL_VERSION,
        "seed": seed,
        "started": started.to_dict(),
        "turns": trace,
        "trace_hash": content_hash(trace),
        "final_world_hash": game.world.state_hash(),
        "event_hash": game.world.event_hash(),
    }
