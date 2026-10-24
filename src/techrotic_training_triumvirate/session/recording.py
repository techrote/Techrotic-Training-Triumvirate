"""Versioned TTT session recording built from canonical semantic records."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from techrotic_training_triumvirate.commands import CommandInterpreter
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommandEnvelope,
    CommanderObservation,
    InterpreterResult,
    JsonObject,
    SchemaRecord,
    SchemaValidationError,
    ScenarioSpec,
    WorldPrivateReference,
    canonical_json,
    content_hash,
    load_record,
)
from techrotic_training_triumvirate.world import (
    ScenarioConfig,
    ScenarioGenerator,
    WorldAuthority,
)

from .render import SemanticDelta, apply_delta, compute_delta

SESSION_RECORDING_SCHEMA = "ttt.session_recording"
SESSION_RECORDING_SCHEMA_VERSION = 1
SESSION_PROTOCOL_VERSION = "ttt-session-v1"


def _expect_object(value: object, *, field: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise SchemaValidationError(f"{field} must be a JSON object")
    return cast(JsonObject, value)


def _expect_str(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(f"{field} must be a string")
    return value


def _expect_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaValidationError(f"{field} must be an integer")
    return value


def _expect_bool(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(f"{field} must be a boolean")
    return value


def _expect_optional_str(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _expect_str(value, field=field)


def _require_keys(
    value: JsonObject,
    *,
    required: set[str],
    field: str,
) -> None:
    actual = set(value)
    missing = required - actual
    extra = actual - required
    if missing or extra:
        raise SchemaValidationError(
            f"{field} keys mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _load[RecordT: SchemaRecord](
    value: object,
    record_type: type[RecordT],
) -> RecordT:
    return cast(RecordT, load_record(value, expected_type=record_type))


@dataclass(frozen=True, slots=True)
class SessionTurn:
    turn_id: int
    observation: CommanderObservation
    action: AssistantAction
    results: tuple[InterpreterResult, ...]
    events: tuple[AuthoritativeEvent, ...]
    next_observation: CommanderObservation
    delta: SemanticDelta
    observation_hash: str
    action_hash: str
    result_hash: str
    event_hash: str
    next_observation_hash: str
    turn_hash: str
    next_world_hash: str

    @classmethod
    def create(
        cls,
        *,
        turn_id: int,
        observation: CommanderObservation,
        action: AssistantAction,
        results: tuple[InterpreterResult, ...],
        events: tuple[AuthoritativeEvent, ...],
        next_observation: CommanderObservation,
        next_world_hash: str,
    ) -> SessionTurn:
        delta = compute_delta(observation, next_observation)
        semantic = {
            "observation": observation.to_dict(),
            "action": action.to_dict(),
            "results": [result.to_dict() for result in results],
            "events": [event.to_dict() for event in events],
            "next_observation": next_observation.to_dict(),
            "next_world_hash": next_world_hash,
        }
        return cls(
            turn_id=turn_id,
            observation=observation,
            action=action,
            results=results,
            events=events,
            next_observation=next_observation,
            delta=delta,
            observation_hash=observation.content_hash(),
            action_hash=action.content_hash(),
            result_hash=content_hash([result.to_dict() for result in results]),
            event_hash=content_hash([event.to_dict() for event in events]),
            next_observation_hash=next_observation.content_hash(),
            turn_hash=content_hash(semantic),
            next_world_hash=next_world_hash,
        )

    def to_dict(self) -> JsonObject:
        return {
            "turn_id": self.turn_id,
            "observation": self.observation.to_dict(),
            "action": self.action.to_dict(),
            "results": [result.to_dict() for result in self.results],
            "events": [event.to_dict() for event in self.events],
            "next_observation": self.next_observation.to_dict(),
            "delta": self.delta.to_dict(),
            "hashes": {
                "observation": self.observation_hash,
                "action": self.action_hash,
                "results": self.result_hash,
                "events": self.event_hash,
                "next_observation": self.next_observation_hash,
                "turn": self.turn_hash,
                "next_world": self.next_world_hash,
            },
        }

    @classmethod
    def from_dict(cls, value: object) -> SessionTurn:
        payload = _expect_object(value, field="session turn")
        _require_keys(
            payload,
            required={
                "turn_id",
                "observation",
                "action",
                "results",
                "events",
                "next_observation",
                "delta",
                "hashes",
            },
            field="session turn",
        )
        results_raw = payload["results"]
        events_raw = payload["events"]
        if not isinstance(results_raw, list):
            raise SchemaValidationError("session turn results must be an array")
        if not isinstance(events_raw, list):
            raise SchemaValidationError("session turn events must be an array")
        delta_raw = _expect_object(payload["delta"], field="session turn delta")
        _require_keys(
            delta_raw,
            required={"base_hash", "target_hash", "set", "remove"},
            field="session turn delta",
        )
        remove_raw = delta_raw["remove"]
        if not isinstance(remove_raw, list) or any(
            not isinstance(item, str) for item in remove_raw
        ):
            raise SchemaValidationError("session turn delta remove must be strings")
        hashes = _expect_object(payload["hashes"], field="session turn hashes")
        _require_keys(
            hashes,
            required={
                "observation",
                "action",
                "results",
                "events",
                "next_observation",
                "turn",
                "next_world",
            },
            field="session turn hashes",
        )
        turn = cls(
            turn_id=_expect_int(payload["turn_id"], field="turn_id"),
            observation=_load(payload["observation"], CommanderObservation),
            action=_load(payload["action"], AssistantAction),
            results=tuple(_load(item, InterpreterResult) for item in results_raw),
            events=tuple(_load(item, AuthoritativeEvent) for item in events_raw),
            next_observation=_load(
                payload["next_observation"], CommanderObservation
            ),
            delta=SemanticDelta(
                base_hash=_expect_str(delta_raw["base_hash"], field="delta.base_hash"),
                target_hash=_expect_str(
                    delta_raw["target_hash"], field="delta.target_hash"
                ),
                set_values=_expect_object(delta_raw["set"], field="delta.set"),
                removed_paths=tuple(cast(list[str], remove_raw)),
            ),
            observation_hash=_expect_str(
                hashes["observation"], field="hashes.observation"
            ),
            action_hash=_expect_str(hashes["action"], field="hashes.action"),
            result_hash=_expect_str(hashes["results"], field="hashes.results"),
            event_hash=_expect_str(hashes["events"], field="hashes.events"),
            next_observation_hash=_expect_str(
                hashes["next_observation"], field="hashes.next_observation"
            ),
            turn_hash=_expect_str(hashes["turn"], field="hashes.turn"),
            next_world_hash=_expect_str(
                hashes["next_world"], field="hashes.next_world"
            ),
        )
        turn.verify_hashes()
        return turn

    def verify_hashes(self) -> None:
        expected = SessionTurn.create(
            turn_id=self.turn_id,
            observation=self.observation,
            action=self.action,
            results=self.results,
            events=self.events,
            next_observation=self.next_observation,
            next_world_hash=self.next_world_hash,
        )
        if self != expected:
            raise SchemaValidationError(
                f"session turn {self.turn_id} semantic hash/delta verification failed"
            )
        reconstructed = apply_delta(self.observation, self.delta)
        if reconstructed != self.next_observation.to_payload():
            raise SchemaValidationError(
                f"session turn {self.turn_id} delta reconstruction failed"
            )


@dataclass(frozen=True, slots=True)
class SessionRecording:
    session_id: str
    run_id: str
    branch_id: str
    parent_branch_id: str | None
    parent_turn_id: int | None
    parent_turn_hash: str | None
    seed: int
    mid_state: bool
    scenario: ScenarioSpec
    initial_world: WorldPrivateReference
    initial_observation: CommanderObservation
    turns: tuple[SessionTurn, ...]
    checkpoint_refs: tuple[str, ...] = ()

    @classmethod
    def new(
        cls,
        *,
        session_id: str,
        run_id: str,
        seed: int,
        mid_state: bool = False,
        branch_id: str = "main",
    ) -> SessionRecording:
        blueprint = ScenarioGenerator().generate(
            seed=seed,
            config=ScenarioConfig(mid_state=mid_state),
        )
        world = WorldAuthority(blueprint)
        return cls(
            session_id=session_id,
            run_id=run_id,
            branch_id=branch_id,
            parent_branch_id=None,
            parent_turn_id=None,
            parent_turn_hash=None,
            seed=seed,
            mid_state=mid_state,
            scenario=blueprint.scenario,
            initial_world=world.world_private_reference(),
            initial_observation=world.commander_observation(turn_id=0),
            turns=(),
            checkpoint_refs=(),
        )

    @property
    def final_world_hash(self) -> str:
        if self.turns:
            return self.turns[-1].next_world_hash
        return self.initial_world.state_hash

    def semantic_projection(self) -> JsonObject:
        return {
            "schema": SESSION_RECORDING_SCHEMA,
            "schema_version": SESSION_RECORDING_SCHEMA_VERSION,
            "protocol_version": SESSION_PROTOCOL_VERSION,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "branch": {
                "branch_id": self.branch_id,
                "parent_branch_id": self.parent_branch_id,
                "parent_turn_id": self.parent_turn_id,
                "parent_turn_hash": self.parent_turn_hash,
            },
            "seed": self.seed,
            "mid_state": self.mid_state,
            "scenario": self.scenario.to_dict(),
            "initial_world": self.initial_world.to_dict(),
            "initial_observation": self.initial_observation.to_dict(),
            "turns": [turn.to_dict() for turn in self.turns],
            "final_world_hash": self.final_world_hash,
        }

    def semantic_hash(self) -> str:
        """Hash semantic TTT content while excluding LangGraph checkpoint IDs."""
        return content_hash(self.semantic_projection())

    def to_dict(self) -> JsonObject:
        value = self.semantic_projection()
        value["orchestration"] = {
            "backend": "langgraph",
            "checkpoint_refs": list(self.checkpoint_refs),
        }
        return value

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def write(self, path: str | Path) -> None:
        destination = Path(path)
        destination.write_text(self.to_json() + "\n", encoding="utf-8")

    def with_checkpoint_ref(self, checkpoint_id: str) -> SessionRecording:
        if checkpoint_id in self.checkpoint_refs:
            return self
        return replace(
            self,
            checkpoint_refs=(*self.checkpoint_refs, checkpoint_id),
        )

    def as_branch(
        self,
        *,
        branch_id: str,
        parent_turn_id: int,
    ) -> SessionRecording:
        if parent_turn_id < 0 or parent_turn_id > len(self.turns):
            raise ValueError("parent_turn_id must identify an existing branch point")
        parent_hash = (
            self.initial_observation.content_hash()
            if parent_turn_id == 0
            else self.turns[parent_turn_id - 1].turn_hash
        )
        return replace(
            self,
            branch_id=branch_id,
            parent_branch_id=self.branch_id,
            parent_turn_id=parent_turn_id,
            parent_turn_hash=parent_hash,
            checkpoint_refs=(),
        )

    @classmethod
    def read(cls, path: str | Path) -> SessionRecording:
        try:
            raw: object = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(f"invalid session JSON: {exc.msg}") from exc
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, value: object) -> SessionRecording:
        payload = _expect_object(value, field="session recording")
        _require_keys(
            payload,
            required={
                "schema",
                "schema_version",
                "protocol_version",
                "session_id",
                "run_id",
                "branch",
                "seed",
                "mid_state",
                "scenario",
                "initial_world",
                "initial_observation",
                "turns",
                "final_world_hash",
                "orchestration",
            },
            field="session recording",
        )
        if payload["schema"] != SESSION_RECORDING_SCHEMA:
            raise SchemaValidationError("unsupported session recording schema")
        if payload["schema_version"] != SESSION_RECORDING_SCHEMA_VERSION:
            raise SchemaValidationError("unsupported session recording schema version")
        if payload["protocol_version"] != SESSION_PROTOCOL_VERSION:
            raise SchemaValidationError("unsupported session protocol version")
        branch = _expect_object(payload["branch"], field="branch")
        _require_keys(
            branch,
            required={
                "branch_id",
                "parent_branch_id",
                "parent_turn_id",
                "parent_turn_hash",
            },
            field="branch",
        )
        parent_turn_id_raw = branch["parent_turn_id"]
        parent_turn_id = (
            None
            if parent_turn_id_raw is None
            else _expect_int(parent_turn_id_raw, field="branch.parent_turn_id")
        )
        turns_raw = payload["turns"]
        if not isinstance(turns_raw, list):
            raise SchemaValidationError("session turns must be an array")
        orchestration = _expect_object(
            payload["orchestration"], field="orchestration"
        )
        _require_keys(
            orchestration,
            required={"backend", "checkpoint_refs"},
            field="orchestration",
        )
        if orchestration["backend"] != "langgraph":
            raise SchemaValidationError("unsupported orchestration backend")
        refs = orchestration["checkpoint_refs"]
        if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
            raise SchemaValidationError("checkpoint_refs must be an array of strings")
        recording = cls(
            session_id=_expect_str(payload["session_id"], field="session_id"),
            run_id=_expect_str(payload["run_id"], field="run_id"),
            branch_id=_expect_str(branch["branch_id"], field="branch.branch_id"),
            parent_branch_id=_expect_optional_str(
                branch["parent_branch_id"], field="branch.parent_branch_id"
            ),
            parent_turn_id=parent_turn_id,
            parent_turn_hash=_expect_optional_str(
                branch["parent_turn_hash"], field="branch.parent_turn_hash"
            ),
            seed=_expect_int(payload["seed"], field="seed"),
            mid_state=_expect_bool(payload["mid_state"], field="mid_state"),
            scenario=_load(payload["scenario"], ScenarioSpec),
            initial_world=_load(payload["initial_world"], WorldPrivateReference),
            initial_observation=_load(
                payload["initial_observation"], CommanderObservation
            ),
            turns=tuple(SessionTurn.from_dict(item) for item in turns_raw),
            checkpoint_refs=tuple(cast(list[str], refs)),
        )
        if _expect_str(payload["final_world_hash"], field="final_world_hash") != (
            recording.final_world_hash
        ):
            raise SchemaValidationError("session final_world_hash mismatch")
        recording.verify()
        return recording

    def verify(self) -> None:
        if self.scenario.identity.seed != self.seed:
            raise SchemaValidationError("session scenario seed mismatch")
        if self.initial_world.scenario != self.scenario.identity:
            raise SchemaValidationError("session initial world scenario mismatch")
        expected_turn_id = 0
        expected_observation = self.initial_observation
        for turn in self.turns:
            if turn.turn_id != expected_turn_id:
                raise SchemaValidationError("session turn_ids must be contiguous")
            if turn.observation != expected_observation:
                raise SchemaValidationError(
                    f"turn {turn.turn_id} observation does not continue prior turn"
                )
            turn.verify_hashes()
            expected_turn_id += 1
            expected_observation = turn.next_observation


def _rebuild_world(recording: SessionRecording) -> WorldAuthority:
    blueprint = ScenarioGenerator().generate(
        seed=recording.seed,
        config=ScenarioConfig(mid_state=recording.mid_state),
    )
    if blueprint.scenario != recording.scenario:
        raise SchemaValidationError("scenario regeneration does not match recording")
    world = WorldAuthority(blueprint)
    if world.world_private_reference() != recording.initial_world:
        raise SchemaValidationError("initial world regeneration does not match recording")
    for prior in recording.turns:
        if len(prior.action.commands) != 1:
            raise SchemaValidationError(
                "session v1 replay requires exactly one command per turn"
            )
        outcome = CommandInterpreter().interpret(prior.action.commands[0], world)
        if outcome.dispatch_event is not None:
            world.events.append(outcome.dispatch_event)
        world.step()
    return world


def execute_turn(
    recording: SessionRecording,
    envelope: CommandEnvelope,
) -> SessionRecording:
    """Execute one model-free session turn and append canonical semantic evidence."""
    world = _rebuild_world(recording)
    turn_id = len(recording.turns)
    observation = world.commander_observation(turn_id=turn_id)
    if observation != (
        recording.initial_observation
        if not recording.turns
        else recording.turns[-1].next_observation
    ):
        raise SchemaValidationError("reconstructed observation drifted before turn")
    before_events = len(world.events)
    outcome = CommandInterpreter().interpret(envelope, world)
    if outcome.dispatch_event is not None:
        world.events.append(outcome.dispatch_event)
    world.step()
    events = tuple(world.events[before_events:])
    action = AssistantAction(commands=(envelope,), communications=())
    next_observation = world.commander_observation(turn_id=turn_id + 1)
    turn = SessionTurn.create(
        turn_id=turn_id,
        observation=observation,
        action=action,
        results=(outcome.result,),
        events=events,
        next_observation=next_observation,
        next_world_hash=world.state_hash(),
    )
    return replace(recording, turns=(*recording.turns, turn))
