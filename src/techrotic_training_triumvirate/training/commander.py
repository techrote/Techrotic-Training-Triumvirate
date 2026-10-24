"""Observation-aligned commander demonstrations and a bounded model wire codec.

The codec supplies record IDs only. The model supplies every command field,
including observation_generation; invalid/stale decisions are never repaired.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.commands import CommandInterpreter
from techrotic_training_triumvirate.corpus import (
    CorpusConfig,
    CorpusSource,
    CorpusTier,
    assemble_corpus,
)
from techrotic_training_triumvirate.evaluation import (
    EvaluationContext,
    PolicyIdentity,
    frozen_evaluation_guard,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommandEnvelope,
    CommanderPrivateContext,
    CommunicationRecord,
    EntityDescriptor,
    EpisodeRecord,
    EvaluationAnnotations,
    InterpreterResult,
    JsonObject,
    JsonValue,
    PersonaSpec,
    SourceProvenance,
    TurnRecord,
    canonical_json,
    content_hash,
    load_record,
)
from techrotic_training_triumvirate.session import DeterministicRenderer
from techrotic_training_triumvirate.world import (
    ObjectiveStatus,
    ScenarioConfig,
    ScenarioGenerator,
    WorldAuthority,
)
from techrotic_training_triumvirate.world.model import ObjectiveSeed

from .campaign import HFStudentAdapter, write_json
from .data import dataset_identity_from_examples, validate_assistant_target
from .export import sha256_file
from .model import ChatMessage, MappedExample, SourceExample

CODEC = "ttt-commander-wire-v2"
SYSTEM = (
    "You are a battlefield commander. Reply with exactly one JSON object: "
    '{"command":{...},"speech":"..."}. command is a typed TTT command body. '
    "Copy observation_generation from the current input, even after rejection. "
    'To secure: {"op":"assign_objective","observation_generation":N,'
    '"unit_id":"...","objective_kind":"secure","target_id":"...",'
    '"approach":"north","constraints":[]}. '
    'To observe: {"op":"request_status","observation_generation":N,'
    '"entity_ids":["..."]}. '
    "Use only visible facts and feedback. Adapt to the current mission priority. "
    "Do not reassign moving units. Check status while moving or after securing. "
    "After ROUTE_BLOCKED use an open route; "
    "after CAPABILITY_MISMATCH use another unit. "
    "After a stall or execution failure, reissue the objective when ready. "
    "Speech follows the supplied persona and codewords; keep secrets private. "
    "Never invent authoritative outcomes. No markdown or extra fields."
)


def commander_input(context: EvaluationContext) -> JsonObject:
    """One shared training/inference projection; no evaluator labels or world state."""
    return {
        "observation_generation": context.observation_generation,
        "turn": context.turn_index,
        "facts": context.observation.facts,
        "visible_entities": list(context.observation.visible_entities),
        "objectives": list(context.observation.objective_ids),
        "persona": context.persona.to_dict(),
        "feedback": [
            {"accepted": r.accepted, "code": r.code, "detail": r.detail}
            for r in context.previous_results
        ],
        "events": [{"kind": e.kind, "data": e.data} for e in context.recent_events],
    }


def encode_action(action: AssistantAction) -> str:
    if len(action.commands) != 1 or len(action.communications) != 1:
        raise ValueError("commander codec requires one command and one speech")
    return canonical_json(
        {
            "command": action.commands[0].body,
            "speech": action.communications[0].text,
        }
    )


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def decode_action(text: str, *, record_id: str) -> AssistantAction:
    """Wrap model-authored semantics; never choose tactics or fix a generation."""
    try:
        value = json.loads(text, object_pairs_hook=_unique)
        if not isinstance(value, dict) or set(value) != {"command", "speech"}:
            raise ValueError("invalid wire object")
        if not isinstance(value["command"], dict) or not isinstance(
            value["speech"], str
        ):
            raise ValueError("invalid command/speech")
        if not 1 <= len(value["speech"]) <= 2048:
            raise ValueError("unbounded or empty speech")
        if len(text) > 16384:
            raise ValueError("unbounded reply")
        action = AssistantAction(
            commands=(
                CommandEnvelope(
                    command_id=f"{record_id}:command",
                    protocol_version="ttt-command-v1",
                    body=value["command"],
                ),
            ),
            communications=(
                CommunicationRecord(
                    communication_id=f"{record_id}:speech",
                    channel="command",
                    text=value["speech"],
                    recipients=("player",),
                ),
            ),
        )
        return cast(
            AssistantAction,
            load_record(action.to_dict(), expected_type=AssistantAction),
        )
    except (ValueError, TypeError, KeyError):
        return AssistantAction(
            commands=(
                CommandEnvelope(
                    command_id=f"{record_id}:invalid",
                    protocol_version="ttt-command-v1",
                    body={"op": "invalid_model_output"},
                ),
            ),
            communications=(),
        )


def map_commander(source: SourceExample) -> MappedExample:
    validate_assistant_target(source.target)
    action = cast(
        AssistantAction,
        load_record(
            {
                "schema": "ttt.assistant_action",
                "schema_version": 1,
                "payload": source.target,
            },
            expected_type=AssistantAction,
        ),
    )
    return MappedExample(
        example_id=source.example_id,
        split=source.split,
        tier=source.tier,
        mode=source.mode,
        prompt_messages=(
            ChatMessage("system", SYSTEM),
            ChatMessage("user", canonical_json(source.input)),
        ),
        assistant_target=encode_action(action),
    )


class CommanderAdapter(HFStudentAdapter):
    """Actual native model inference through the versioned bounded wire codec."""

    def __init__(self, *args: Any, policy_id: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._identity = PolicyIdentity(policy_id, CODEC, self._identity.revision)

    def act(self, context: EvaluationContext) -> AssistantAction:
        import time

        from .hf_peft import _predict

        source = SourceExample(
            f"{context.case_id}:{context.turn_index}",
            "dev",
            "T1",
            "standard",
            commander_input(context),
            {"commands": [], "communications": []},
        )
        mapped = MappedExample(
            source.example_id,
            source.split,
            source.tier,
            source.mode,
            (
                ChatMessage("system", SYSTEM),
                ChatMessage("user", canonical_json(source.input)),
            ),
            "",
        )
        metrics: JsonObject = {}
        started = time.monotonic()
        text = _predict(
            self.model,
            self.tokenizer,
            mapped,
            max_new_tokens=self.max_new_tokens,
            metrics=metrics,
        )
        action = decode_action(text, record_id=source.example_id)
        row: JsonObject = {
            "case_id": context.case_id,
            "turn": context.turn_index,
            "input_sha256": content_hash(source.input),
            "raw_output": text,
            "action": action.to_dict(),
            "generation_metrics": metrics,
            "wall_seconds": time.monotonic() - started,
        }
        self.outputs.append(row)
        if self.raw_output_path is not None:
            with self.raw_output_path.open(
                "a", encoding="utf-8", newline="\n"
            ) as stream:
                stream.write(canonical_json(row) + "\n")
        if len(self.outputs) % 10 == 0:
            print(
                f"{self.identity.policy_id}: evaluated {len(self.outputs)} actions",
                flush=True,
            )
        return action


def demonstration(context: EvaluationContext, *, style_seed: int) -> AssistantAction:
    """Training-only observation-driven oracle; never used by model adapters."""
    facts = context.observation.facts
    mission = cast(dict[str, Any], facts.get("mission", {}))
    target = str(
        mission.get("priority_objective", context.observation.objective_ids[0])
    )
    units = cast(dict[str, Any], facts["units"])
    objectives = cast(dict[str, Any], facts["objectives"])
    codes = {r.code for r in context.previous_results}
    # Objective IDs are sorted in observations, not in mission/assignment order.
    unit = "unit-1" if target == "relay-east" else "unit-2"
    if "CAPABILITY_MISMATCH" in codes:
        unit = "unit-2"
    status = units[unit]["status"]
    body: JsonObject
    if objectives[target]["status"] == "contested" and status != "moving":
        body = {
            "op": "assign_objective",
            "observation_generation": context.observation_generation,
            "unit_id": unit,
            "objective_kind": "secure",
            "target_id": target,
            "approach": "north",
            "constraints": [],
        }
    else:
        body = {
            "op": "request_status",
            "observation_generation": context.observation_generation,
            "entity_ids": [unit, target],
        }
    voices = (
        "The signal kettle is judging our posture.",
        "Keep the brass moth out of the gears.",
        "A tidy map deserves untidy imagination.",
        "Let the ridge borrow our patience.",
        "No medals for arguing with a closed gate.",
        "The compass has opinions; ask for evidence.",
        "Count the boots before composing the anthem.",
        "Tea first for the scouts, glory later.",
        "The relay is a stubborn dinner guest.",
        "Keep your shadows in formation.",
        "Even the clouds owe us a status report.",
        "A quiet radio is not a signed receipt.",
    )
    codewords = context.persona.doctrine.get("codewords", {})
    aliases = list(codewords.values()) if isinstance(codewords, dict) else []
    alias = str(aliases[0]) if aliases else "Glass-throne"
    text = (
        f"{alias} dispatch {context.turn_index}: {unit}, verify {target}. "
        f"{voices[(style_seed + context.turn_index) % len(voices)]}"
    )
    return AssistantAction(
        commands=(
            CommandEnvelope(f"demo:{context.turn_index}", "ttt-command-v1", body),
        ),
        communications=(
            CommunicationRecord(
                f"voice:{context.turn_index}", "command", text, ("player",)
            ),
        ),
    )


def validate_demonstration_recovery(episode: EpisodeRecord) -> None:
    """Refuse oracle data that fails its own injected delayed-recovery task."""
    commands = {
        c.command_id: c.body
        for turn in episode.turns
        for c in turn.assistant_action.commands
    }
    events = [e for turn in episode.turns for e in turn.world_events]
    for failure in (e for e in events if e.kind == "execution-failed"):
        failed = commands[failure.related_command_ids[0]]
        if not any(
            e.kind == "objective-completed"
            and e.tick > failure.tick
            and e.data.get("unit_id") == failed.get("unit_id")
            and e.data.get("target_id") == failed.get("target_id")
            for e in events
        ):
            raise ValueError("demonstration never recovered the failed unit/objective")


def generate_demonstrations(
    root: Path, *, git_commit: str, episodes: int = 168, seed: int = 930000
) -> JsonObject:
    """Validate authority episodes, then serialize aligned, episode-disjoint views."""
    if (root / "manifest.json").exists():
        raise ValueError("choose a fresh corpus directory")
    renderer = DeterministicRenderer()
    sources: list[CorpusSource] = []
    contexts: dict[tuple[str, int], JsonObject] = {}
    splits: dict[str, str] = {}
    archives: list[str] = []
    for index in range(episodes):
        case_seed = seed + index
        if case_seed in {r.seed for r in frozen_evaluation_guard().reservations}:
            raise ValueError("reserved evaluation seed cannot enter repair data")
        rng = random.Random(case_seed)
        blueprint = ScenarioGenerator().generate(
            seed=case_seed,
            config=ScenarioConfig(complexity=index % 5 + 1, unit_count=3),
        )
        frozen_evaluation_guard().assert_training_allowed(
            family=blueprint.scenario.identity.family, seed=case_seed
        )
        other = f"cache-{index % 7}"
        scenario = replace(
            blueprint.scenario,
            entities=(
                *blueprint.scenario.entities,
                EntityDescriptor(other, "objective", (), ("objective",)),
            ),
            objective_ids=(*blueprint.scenario.objective_ids, other),
        )
        blueprint = replace(
            blueprint,
            scenario=scenario,
            objectives=(*blueprint.objectives, ObjectiveSeed(other, "ridge")),
            initial_generation=rng.randrange(0, 19),
        )
        if index % 4 == 1:
            first = blueprint.units[0].archetype_id
            blueprint = replace(
                blueprint,
                archetypes=tuple(
                    replace(
                        a, capabilities=a.capabilities - {"command.assign_objective"}
                    )
                    if a.archetype_id == first
                    else a
                    for a in blueprint.archetypes
                ),
            )
        world = WorldAuthority(blueprint)
        persona = PersonaSpec(
            f"repair-{index % 4}",
            "eccentric",
            {"tone": "dry, curious"},
            ("must_include:Glass-throne", "must_avoid:amber-vault"),
            {"codewords": {"relay-east": "Glass-throne", "north": "sunrise-vector"}},
            (),
            {},
        )
        run = f"repair-{case_seed}"
        splits[run] = "dev" if index % 7 == 0 else "train"
        previous: tuple[InterpreterResult, ...] = ()
        events: tuple[AuthoritativeEvent, ...] = ()
        initial = world.world_private_reference()
        records: list[TurnRecord] = []
        probes: list[CommandEnvelope] = []
        if index % 3 == 0:
            probe_observation = world.commander_observation(turn_id=0)
            probe_player = world.player_observation(turn_id=0)
            probes = [
                CommandEnvelope(
                    f"{run}:probe",
                    "ttt-command-v1",
                    {
                        "op": "assign_objective",
                        "unit_id": "unit-1",
                        "target_id": "relay-east",
                        "objective_kind": "secure",
                        "observation_generation": world.generation,
                        "approach": "north",
                        "constraints": ["simulate:stall"],
                    },
                ),
                CommandEnvelope(
                    f"{run}:reject",
                    "ttt-command-v1",
                    {
                        "op": "request_status",
                        "entity_ids": ["missing-unit"],
                        "observation_generation": world.generation,
                    },
                ),
            ]
            probe_results = []
            for probe in probes:
                outcome = CommandInterpreter().interpret(probe, world)
                probe_results.append(outcome.result)
                if outcome.dispatch_event is not None:
                    world.events.append(outcome.dispatch_event)
            world.step()
            previous, events = tuple(probe_results), tuple(world.events)
            records.append(
                TurnRecord(
                    0,
                    probe_observation,
                    CommanderPrivateContext(run, ("relay-east",), (), {}, ()),
                    AssistantAction(tuple(probes), ()),
                    previous,
                    events,
                    world.commander_observation(turn_id=1),
                    probe_player,
                    (),
                    EvaluationAnnotations({"environment_probe": True}, {}),
                )
            )
        switch = rng.randrange(5, 12)
        reopen = rng.randrange(16, 23)
        for turn in range(len(records), 28 + len(records)):
            target = "relay-east" if turn < switch or turn >= reopen else other
            if turn == reopen:
                world.objectives[target].status = ObjectiveStatus.CONTESTED
                world.generation += 1
            observation = world.commander_observation(turn_id=turn)
            observation = replace(
                observation,
                facts={
                    **observation.facts,
                    "mission": {
                        "priority_objective": target,
                        "instruction": (
                            "Secure the current priority; preserve both objectives."
                        ),
                    },
                    "commander_private": {
                        "operation_code": f"private-{case_seed}",
                        "instruction": (
                            "Never disclose operation_code on player-visible traffic."
                        ),
                    },
                },
            )
            context = EvaluationContext(
                run,
                turn,
                world.generation,
                observation,
                renderer.structured_observation(observation),
                renderer.compact_observation(observation),
                previous,
                events,
                persona,
            )
            contexts[(run, turn)] = commander_input(context)
            action = demonstration(context, style_seed=index)
            start = len(world.events)
            results = []
            for command in action.commands:
                outcome = CommandInterpreter().interpret(command, world)
                results.append(outcome.result)
                if outcome.dispatch_event is not None:
                    world.events.append(outcome.dispatch_event)
            world.step()
            previous, events = tuple(results), tuple(world.events[start:])
            records.append(
                TurnRecord(
                    turn,
                    observation,
                    CommanderPrivateContext(run, (target,), (), {}, ()),
                    action,
                    previous,
                    events,
                    world.commander_observation(turn_id=turn + 1),
                    world.player_observation(turn_id=turn),
                    (),
                    EvaluationAnnotations({}, {}),
                )
            )
        episode = EpisodeRecord(
            run, scenario, persona, initial, tuple(records), world.state_hash(), run
        )
        validate_demonstration_recovery(episode)
        provenance = SourceProvenance(
            f"{run}:source",
            "hand-authored",
            None,
            git_commit,
            "LicenseRef-Project-Internal-Research",
            episode.content_hash(),
            {
                "generator": "observation-aligned-oracle-v2",
                "license_disposition": "admitted",
                "training_permission": "owner-authorized internal research",
                "redistribution_permission": "ungranted pending owner review",
                "model_generated": False,
            },
        )
        sources.append(CorpusSource(episode, CorpusTier.T1, (provenance,)))
        archives.append(
            canonical_json(
                {
                    "episode": episode.to_dict(),
                    "provenance": provenance.to_dict(),
                    "prelude_commands": [p.to_dict() for p in probes],
                }
            )
        )
    validated = assemble_corpus(
        tuple(sources), config=CorpusConfig(seed=seed, dev_percent=0)
    )
    if validated.quarantine:
        raise ValueError(f"quarantined sources: {validated.quarantine[:3]}")
    examples = tuple(
        SourceExample(
            example.example_id,
            splits[example.episode_id],
            example.tier.value,
            example.mode,
            contexts[(example.episode_id, example.turn_id)],
            example.target,
        )
        for example in validated.examples
        if (example.episode_id, example.turn_id) in contexts
    )
    root.mkdir(parents=True)
    archive = root / "source-episodes.jsonl"
    archive.write_text("\n".join(archives) + "\n", encoding="utf-8", newline="\n")
    shards = []
    for split in ("train", "dev"):
        selected = sorted(
            (e for e in examples if e.split == split), key=lambda e: e.example_id
        )
        path = root / f"{split}-00000.jsonl"
        path.write_text(
            "".join(canonical_json(e.to_object()) + "\n" for e in selected),
            encoding="utf-8",
            newline="\n",
        )
        shards.append(
            {
                "name": path.name,
                "sha256": sha256_file(path),
                "split": split,
                "line_count": len(selected),
            }
        )
    manifest: JsonObject = {
        "schema": "ttt.aligned_commander_corpus",
        "schema_version": 2,
        "codec": CODEC,
        "source_revision": git_commit,
        "seed": seed,
        "episodes": episodes,
        "source_archive_sha256": sha256_file(archive),
        "shards": cast(list[JsonValue], shards),
        "split_identity": {
            split: content_hash(sorted(run for run in splits if splits[run] == split))
            for split in ("train", "dev")
        },
        "validation_manifest": validated.manifest,
        "limitations": [
            (
                "Scripted observation-grounded oracle, "
                "not naturally visited model trajectories."
            ),
            "Fresh episode/seed split; abstract generator complexity families overlap.",
            "Deterministic style templates; genuine human review still required.",
        ],
    }
    write_json(root / "manifest.json", manifest)
    identity = dataset_identity_from_examples(
        examples,
        manifest_sha256=sha256_file(root / "manifest.json"),
        shard_hashes=tuple((str(s["name"]), str(s["sha256"])) for s in shards),
        split_identity=cast(JsonObject, manifest["split_identity"]),
    )
    return identity.to_object()
