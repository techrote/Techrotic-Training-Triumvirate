"""Canonical TTT schema v1 records.

The command body intentionally remains opaque until TTT-003 defines the command IR.
All durable records still carry their own schema name/version envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, cast

from .base import (
    JsonObject,
    JsonValue,
    SchemaRecord,
    SchemaValidationError,
    load_record,
    register_record,
    require_bool,
    require_exact_keys,
    require_int,
    require_json_object,
    require_optional_str,
    require_str,
    require_str_tuple,
)


def _record[RecordT: SchemaRecord](
    value: object,
    expected: type[RecordT],
    *,
    field: str,
) -> RecordT:
    try:
        loaded = load_record(value, expected_type=expected)
    except ValueError as exc:
        raise SchemaValidationError(f"{field}: {exc}") from exc
    return cast(RecordT, loaded)


def _record_tuple[RecordT: SchemaRecord](
    value: object,
    expected: type[RecordT],
    *,
    field: str,
) -> tuple[RecordT, ...]:
    if not isinstance(value, list):
        raise SchemaValidationError(f"{field} must be an array")
    return tuple(
        _record(item, expected, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _record_list(records: tuple[SchemaRecord, ...]) -> list[JsonValue]:
    return [record.to_dict() for record in records]


@register_record
@dataclass(frozen=True, slots=True)
class ScenarioIdentity(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.scenario_identity"
    scenario_id: str
    family: str
    generator: str
    generator_version: str
    seed: int

    def to_payload(self) -> JsonObject:
        return {
            "scenario_id": self.scenario_id,
            "family": self.family,
            "generator": self.generator,
            "generator_version": self.generator_version,
            "seed": self.seed,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> ScenarioIdentity:
        require_exact_keys(
            payload,
            required={
                "scenario_id",
                "family",
                "generator",
                "generator_version",
                "seed",
            },
        )
        return cls(
            scenario_id=require_str(payload["scenario_id"], field="scenario_id"),
            family=require_str(payload["family"], field="family"),
            generator=require_str(payload["generator"], field="generator"),
            generator_version=require_str(
                payload["generator_version"], field="generator_version"
            ),
            seed=require_int(payload["seed"], field="seed"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class CapabilityDescriptor(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.capability"
    capability_id: str
    parameters: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "capability_id": self.capability_id,
            "parameters": self.parameters,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> CapabilityDescriptor:
        require_exact_keys(
            payload,
            required={"capability_id", "parameters"},
        )
        return cls(
            capability_id=require_str(payload["capability_id"], field="capability_id"),
            parameters=require_json_object(payload["parameters"], field="parameters"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class EntityDescriptor(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.entity"
    entity_id: str
    kind: str
    capabilities: tuple[CapabilityDescriptor, ...]
    tags: tuple[str, ...]

    def to_payload(self) -> JsonObject:
        return {
            "entity_id": self.entity_id,
            "kind": self.kind,
            "capabilities": _record_list(self.capabilities),
            "tags": list(self.tags),
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> EntityDescriptor:
        require_exact_keys(
            payload,
            required={"entity_id", "kind", "capabilities", "tags"},
        )
        return cls(
            entity_id=require_str(payload["entity_id"], field="entity_id"),
            kind=require_str(payload["kind"], field="kind"),
            capabilities=_record_tuple(
                payload["capabilities"],
                CapabilityDescriptor,
                field="capabilities",
            ),
            tags=require_str_tuple(payload["tags"], field="tags"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class ScenarioSpec(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.scenario"
    identity: ScenarioIdentity
    entities: tuple[EntityDescriptor, ...]
    objective_ids: tuple[str, ...]
    topology_refs: tuple[str, ...]
    metadata: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "identity": self.identity.to_dict(),
            "entities": _record_list(self.entities),
            "objective_ids": list(self.objective_ids),
            "topology_refs": list(self.topology_refs),
            "metadata": self.metadata,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> ScenarioSpec:
        require_exact_keys(
            payload,
            required={
                "identity",
                "entities",
                "objective_ids",
                "topology_refs",
                "metadata",
            },
        )
        return cls(
            identity=_record(
                payload["identity"],
                ScenarioIdentity,
                field="identity",
            ),
            entities=_record_tuple(
                payload["entities"],
                EntityDescriptor,
                field="entities",
            ),
            objective_ids=require_str_tuple(
                payload["objective_ids"], field="objective_ids"
            ),
            topology_refs=require_str_tuple(
                payload["topology_refs"], field="topology_refs"
            ),
            metadata=require_json_object(payload["metadata"], field="metadata"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class WorldPrivateReference(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.world_private_reference"
    state_id: str
    scenario: ScenarioIdentity
    state_hash: str
    generation: int
    secret_ids: tuple[str, ...]

    def to_payload(self) -> JsonObject:
        return {
            "state_id": self.state_id,
            "scenario": self.scenario.to_dict(),
            "state_hash": self.state_hash,
            "generation": self.generation,
            "secret_ids": list(self.secret_ids),
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> WorldPrivateReference:
        require_exact_keys(
            payload,
            required={
                "state_id",
                "scenario",
                "state_hash",
                "generation",
                "secret_ids",
            },
        )
        return cls(
            state_id=require_str(payload["state_id"], field="state_id"),
            scenario=_record(
                payload["scenario"],
                ScenarioIdentity,
                field="scenario",
            ),
            state_hash=require_str(payload["state_hash"], field="state_hash"),
            generation=require_int(payload["generation"], field="generation"),
            secret_ids=require_str_tuple(payload["secret_ids"], field="secret_ids"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class CommanderObservation(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.commander_observation"
    turn_id: int
    world_state_id: str
    visible_entities: tuple[str, ...]
    objective_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    facts: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "turn_id": self.turn_id,
            "world_state_id": self.world_state_id,
            "visible_entities": list(self.visible_entities),
            "objective_ids": list(self.objective_ids),
            "event_ids": list(self.event_ids),
            "facts": self.facts,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> CommanderObservation:
        require_exact_keys(
            payload,
            required={
                "turn_id",
                "world_state_id",
                "visible_entities",
                "objective_ids",
                "event_ids",
                "facts",
            },
        )
        return cls(
            turn_id=require_int(payload["turn_id"], field="turn_id"),
            world_state_id=require_str(
                payload["world_state_id"], field="world_state_id"
            ),
            visible_entities=require_str_tuple(
                payload["visible_entities"], field="visible_entities"
            ),
            objective_ids=require_str_tuple(
                payload["objective_ids"], field="objective_ids"
            ),
            event_ids=require_str_tuple(payload["event_ids"], field="event_ids"),
            facts=require_json_object(payload["facts"], field="facts"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class CommanderPrivateContext(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.commander_private_context"
    commander_id: str
    goals: tuple[str, ...]
    secret_ids: tuple[str, ...]
    beliefs: JsonObject
    memory_refs: tuple[str, ...]

    def to_payload(self) -> JsonObject:
        return {
            "commander_id": self.commander_id,
            "goals": list(self.goals),
            "secret_ids": list(self.secret_ids),
            "beliefs": self.beliefs,
            "memory_refs": list(self.memory_refs),
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> CommanderPrivateContext:
        require_exact_keys(
            payload,
            required={
                "commander_id",
                "goals",
                "secret_ids",
                "beliefs",
                "memory_refs",
            },
        )
        return cls(
            commander_id=require_str(payload["commander_id"], field="commander_id"),
            goals=require_str_tuple(payload["goals"], field="goals"),
            secret_ids=require_str_tuple(payload["secret_ids"], field="secret_ids"),
            beliefs=require_json_object(payload["beliefs"], field="beliefs"),
            memory_refs=require_str_tuple(payload["memory_refs"], field="memory_refs"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class PlayerObservation(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.player_observation"
    turn_id: int
    visible_entities: tuple[str, ...]
    event_ids: tuple[str, ...]
    facts: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "turn_id": self.turn_id,
            "visible_entities": list(self.visible_entities),
            "event_ids": list(self.event_ids),
            "facts": self.facts,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> PlayerObservation:
        require_exact_keys(
            payload,
            required={"turn_id", "visible_entities", "event_ids", "facts"},
        )
        return cls(
            turn_id=require_int(payload["turn_id"], field="turn_id"),
            visible_entities=require_str_tuple(
                payload["visible_entities"], field="visible_entities"
            ),
            event_ids=require_str_tuple(payload["event_ids"], field="event_ids"),
            facts=require_json_object(payload["facts"], field="facts"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class PlayerInterceptEnvelope(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.player_intercept"
    intercept_id: str
    source_event_ids: tuple[str, ...]
    payload: JsonObject
    is_deception: bool
    deception_event_id: str | None

    def to_payload(self) -> JsonObject:
        return {
            "intercept_id": self.intercept_id,
            "source_event_ids": list(self.source_event_ids),
            "payload": self.payload,
            "is_deception": self.is_deception,
            "deception_event_id": self.deception_event_id,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> PlayerInterceptEnvelope:
        require_exact_keys(
            payload,
            required={
                "intercept_id",
                "source_event_ids",
                "payload",
                "is_deception",
                "deception_event_id",
            },
        )
        is_deception = require_bool(payload["is_deception"], field="is_deception")
        deception_event_id = require_optional_str(
            payload["deception_event_id"], field="deception_event_id"
        )
        if is_deception and deception_event_id is None:
            raise SchemaValidationError(
                "deception_event_id is required when is_deception is true"
            )
        if not is_deception and deception_event_id is not None:
            raise SchemaValidationError(
                "deception_event_id must be null for ordinary intercepts"
            )
        return cls(
            intercept_id=require_str(payload["intercept_id"], field="intercept_id"),
            source_event_ids=require_str_tuple(
                payload["source_event_ids"], field="source_event_ids"
            ),
            payload=require_json_object(payload["payload"], field="payload"),
            is_deception=is_deception,
            deception_event_id=deception_event_id,
        )


@register_record
@dataclass(frozen=True, slots=True)
class PersonaSpec(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.persona"
    persona_id: str
    archetype: str
    traits: JsonObject
    speech_constraints: tuple[str, ...]
    doctrine: JsonObject
    secret_ids: tuple[str, ...]
    tactical_biases: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "persona_id": self.persona_id,
            "archetype": self.archetype,
            "traits": self.traits,
            "speech_constraints": list(self.speech_constraints),
            "doctrine": self.doctrine,
            "secret_ids": list(self.secret_ids),
            "tactical_biases": self.tactical_biases,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> PersonaSpec:
        require_exact_keys(
            payload,
            required={
                "persona_id",
                "archetype",
                "traits",
                "speech_constraints",
                "doctrine",
                "secret_ids",
                "tactical_biases",
            },
        )
        return cls(
            persona_id=require_str(payload["persona_id"], field="persona_id"),
            archetype=require_str(payload["archetype"], field="archetype"),
            traits=require_json_object(payload["traits"], field="traits"),
            speech_constraints=require_str_tuple(
                payload["speech_constraints"], field="speech_constraints"
            ),
            doctrine=require_json_object(payload["doctrine"], field="doctrine"),
            secret_ids=require_str_tuple(payload["secret_ids"], field="secret_ids"),
            tactical_biases=require_json_object(
                payload["tactical_biases"], field="tactical_biases"
            ),
        )


@register_record
@dataclass(frozen=True, slots=True)
class CommandEnvelope(SchemaRecord):
    """Versioned opaque command wrapper; TTT-003 owns command body semantics."""

    SCHEMA_NAME: ClassVar[str] = "ttt.command_envelope"
    command_id: str
    protocol_version: str
    body: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "command_id": self.command_id,
            "protocol_version": self.protocol_version,
            "body": self.body,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> CommandEnvelope:
        require_exact_keys(
            payload,
            required={"command_id", "protocol_version", "body"},
        )
        return cls(
            command_id=require_str(payload["command_id"], field="command_id"),
            protocol_version=require_str(
                payload["protocol_version"], field="protocol_version"
            ),
            body=require_json_object(payload["body"], field="body"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class CommunicationRecord(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.communication"
    communication_id: str
    channel: str
    text: str
    recipients: tuple[str, ...]

    def to_payload(self) -> JsonObject:
        return {
            "communication_id": self.communication_id,
            "channel": self.channel,
            "text": self.text,
            "recipients": list(self.recipients),
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> CommunicationRecord:
        require_exact_keys(
            payload,
            required={"communication_id", "channel", "text", "recipients"},
        )
        return cls(
            communication_id=require_str(
                payload["communication_id"], field="communication_id"
            ),
            channel=require_str(payload["channel"], field="channel"),
            text=require_str(payload["text"], field="text"),
            recipients=require_str_tuple(payload["recipients"], field="recipients"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class AssistantAction(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.assistant_action"
    commands: tuple[CommandEnvelope, ...]
    communications: tuple[CommunicationRecord, ...]

    def to_payload(self) -> JsonObject:
        return {
            "commands": _record_list(self.commands),
            "communications": _record_list(self.communications),
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> AssistantAction:
        require_exact_keys(
            payload,
            required={"commands", "communications"},
        )
        return cls(
            commands=_record_tuple(
                payload["commands"], CommandEnvelope, field="commands"
            ),
            communications=_record_tuple(
                payload["communications"],
                CommunicationRecord,
                field="communications",
            ),
        )


@register_record
@dataclass(frozen=True, slots=True)
class InterpreterResult(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.interpreter_result"
    command_id: str
    accepted: bool
    code: str
    detail: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "command_id": self.command_id,
            "accepted": self.accepted,
            "code": self.code,
            "detail": self.detail,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> InterpreterResult:
        require_exact_keys(
            payload,
            required={"command_id", "accepted", "code", "detail"},
        )
        return cls(
            command_id=require_str(payload["command_id"], field="command_id"),
            accepted=require_bool(payload["accepted"], field="accepted"),
            code=require_str(payload["code"], field="code"),
            detail=require_json_object(payload["detail"], field="detail"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class AuthoritativeEvent(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.authoritative_event"
    event_id: str
    kind: str
    tick: int
    related_command_ids: tuple[str, ...]
    data: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "tick": self.tick,
            "related_command_ids": list(self.related_command_ids),
            "data": self.data,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> AuthoritativeEvent:
        require_exact_keys(
            payload,
            required={
                "event_id",
                "kind",
                "tick",
                "related_command_ids",
                "data",
            },
        )
        return cls(
            event_id=require_str(payload["event_id"], field="event_id"),
            kind=require_str(payload["kind"], field="kind"),
            tick=require_int(payload["tick"], field="tick"),
            related_command_ids=require_str_tuple(
                payload["related_command_ids"], field="related_command_ids"
            ),
            data=require_json_object(payload["data"], field="data"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class EvaluationAnnotations(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.evaluation_annotations"
    labels: JsonObject
    evaluator_only: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "labels": self.labels,
            "evaluator_only": self.evaluator_only,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> EvaluationAnnotations:
        require_exact_keys(
            payload,
            required={"labels", "evaluator_only"},
        )
        return cls(
            labels=require_json_object(payload["labels"], field="labels"),
            evaluator_only=require_json_object(
                payload["evaluator_only"], field="evaluator_only"
            ),
        )


@register_record
@dataclass(frozen=True, slots=True)
class TurnRecord(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.turn"
    turn_id: int
    observation: CommanderObservation
    commander_private_context: CommanderPrivateContext
    assistant_action: AssistantAction
    interpreter_results: tuple[InterpreterResult, ...]
    world_events: tuple[AuthoritativeEvent, ...]
    next_observation: CommanderObservation
    player_observation: PlayerObservation
    player_intercepts: tuple[PlayerInterceptEnvelope, ...]
    annotations: EvaluationAnnotations

    def to_payload(self) -> JsonObject:
        return {
            "turn_id": self.turn_id,
            "observation": self.observation.to_dict(),
            "commander_private_context": self.commander_private_context.to_dict(),
            "assistant_action": self.assistant_action.to_dict(),
            "interpreter_results": _record_list(self.interpreter_results),
            "world_events": _record_list(self.world_events),
            "next_observation": self.next_observation.to_dict(),
            "player_observation": self.player_observation.to_dict(),
            "player_intercepts": _record_list(self.player_intercepts),
            "annotations": self.annotations.to_dict(),
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> TurnRecord:
        require_exact_keys(
            payload,
            required={
                "turn_id",
                "observation",
                "commander_private_context",
                "assistant_action",
                "interpreter_results",
                "world_events",
                "next_observation",
                "player_observation",
                "player_intercepts",
                "annotations",
            },
        )
        turn_id = require_int(payload["turn_id"], field="turn_id")
        observation = _record(
            payload["observation"], CommanderObservation, field="observation"
        )
        next_observation = _record(
            payload["next_observation"],
            CommanderObservation,
            field="next_observation",
        )
        if observation.turn_id != turn_id:
            raise SchemaValidationError("turn observation.turn_id must equal turn_id")
        if next_observation.turn_id != turn_id + 1:
            raise SchemaValidationError(
                "next_observation.turn_id must equal turn_id + 1"
            )
        return cls(
            turn_id=turn_id,
            observation=observation,
            commander_private_context=_record(
                payload["commander_private_context"],
                CommanderPrivateContext,
                field="commander_private_context",
            ),
            assistant_action=_record(
                payload["assistant_action"],
                AssistantAction,
                field="assistant_action",
            ),
            interpreter_results=_record_tuple(
                payload["interpreter_results"],
                InterpreterResult,
                field="interpreter_results",
            ),
            world_events=_record_tuple(
                payload["world_events"],
                AuthoritativeEvent,
                field="world_events",
            ),
            next_observation=next_observation,
            player_observation=_record(
                payload["player_observation"],
                PlayerObservation,
                field="player_observation",
            ),
            player_intercepts=_record_tuple(
                payload["player_intercepts"],
                PlayerInterceptEnvelope,
                field="player_intercepts",
            ),
            annotations=_record(
                payload["annotations"],
                EvaluationAnnotations,
                field="annotations",
            ),
        )


@register_record
@dataclass(frozen=True, slots=True)
class SourceProvenance(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.source_provenance"
    source_id: str
    source_class: str
    uri: str | None
    revision: str | None
    license_id: str | None
    source_content_hash: str | None
    metadata: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "source_id": self.source_id,
            "source_class": self.source_class,
            "uri": self.uri,
            "revision": self.revision,
            "license_id": self.license_id,
            "source_content_hash": self.source_content_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> SourceProvenance:
        require_exact_keys(
            payload,
            required={
                "source_id",
                "source_class",
                "uri",
                "revision",
                "license_id",
                "source_content_hash",
                "metadata",
            },
        )
        return cls(
            source_id=require_str(payload["source_id"], field="source_id"),
            source_class=require_str(payload["source_class"], field="source_class"),
            uri=require_optional_str(payload["uri"], field="uri"),
            revision=require_optional_str(payload["revision"], field="revision"),
            license_id=require_optional_str(payload["license_id"], field="license_id"),
            source_content_hash=require_optional_str(
                payload["source_content_hash"], field="source_content_hash"
            ),
            metadata=require_json_object(payload["metadata"], field="metadata"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class RunManifest(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.run_manifest"
    run_id: str
    git_commit: str
    schema_versions: JsonObject
    seeds: JsonObject
    generator_config: JsonObject
    source_refs: tuple[str, ...]
    parent_run_ids: tuple[str, ...]
    artifact_hashes: JsonObject
    command_line: tuple[str, ...]
    runtime: JsonObject

    def to_payload(self) -> JsonObject:
        return {
            "run_id": self.run_id,
            "git_commit": self.git_commit,
            "schema_versions": self.schema_versions,
            "seeds": self.seeds,
            "generator_config": self.generator_config,
            "source_refs": list(self.source_refs),
            "parent_run_ids": list(self.parent_run_ids),
            "artifact_hashes": self.artifact_hashes,
            "command_line": list(self.command_line),
            "runtime": self.runtime,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> RunManifest:
        require_exact_keys(
            payload,
            required={
                "run_id",
                "git_commit",
                "schema_versions",
                "seeds",
                "generator_config",
                "source_refs",
                "parent_run_ids",
                "artifact_hashes",
                "command_line",
                "runtime",
            },
        )
        return cls(
            run_id=require_str(payload["run_id"], field="run_id"),
            git_commit=require_str(payload["git_commit"], field="git_commit"),
            schema_versions=require_json_object(
                payload["schema_versions"], field="schema_versions"
            ),
            seeds=require_json_object(payload["seeds"], field="seeds"),
            generator_config=require_json_object(
                payload["generator_config"], field="generator_config"
            ),
            source_refs=require_str_tuple(payload["source_refs"], field="source_refs"),
            parent_run_ids=require_str_tuple(
                payload["parent_run_ids"], field="parent_run_ids"
            ),
            artifact_hashes=require_json_object(
                payload["artifact_hashes"], field="artifact_hashes"
            ),
            command_line=require_str_tuple(
                payload["command_line"], field="command_line"
            ),
            runtime=require_json_object(payload["runtime"], field="runtime"),
        )


@register_record
@dataclass(frozen=True, slots=True)
class EpisodeRecord(SchemaRecord):
    SCHEMA_NAME: ClassVar[str] = "ttt.episode"
    episode_id: str
    scenario: ScenarioSpec
    persona: PersonaSpec
    initial_world: WorldPrivateReference
    turns: tuple[TurnRecord, ...]
    final_world_hash: str
    run_id: str

    def to_payload(self) -> JsonObject:
        return {
            "episode_id": self.episode_id,
            "scenario": self.scenario.to_dict(),
            "persona": self.persona.to_dict(),
            "initial_world": self.initial_world.to_dict(),
            "turns": _record_list(self.turns),
            "final_world_hash": self.final_world_hash,
            "run_id": self.run_id,
        }

    @classmethod
    def from_payload(cls, payload: JsonObject) -> EpisodeRecord:
        require_exact_keys(
            payload,
            required={
                "episode_id",
                "scenario",
                "persona",
                "initial_world",
                "turns",
                "final_world_hash",
                "run_id",
            },
        )
        turns = _record_tuple(payload["turns"], TurnRecord, field="turns")
        for previous, current in zip(turns, turns[1:], strict=False):
            if current.turn_id != previous.turn_id + 1:
                raise SchemaValidationError(
                    "episode turn_ids must be contiguous and increasing"
                )
        return cls(
            episode_id=require_str(payload["episode_id"], field="episode_id"),
            scenario=_record(payload["scenario"], ScenarioSpec, field="scenario"),
            persona=_record(payload["persona"], PersonaSpec, field="persona"),
            initial_world=_record(
                payload["initial_world"],
                WorldPrivateReference,
                field="initial_world",
            ),
            turns=turns,
            final_world_hash=require_str(
                payload["final_world_hash"], field="final_world_hash"
            ),
            run_id=require_str(payload["run_id"], field="run_id"),
        )
