"""Deterministic corpus validation, split generation, and JSONL assembly."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from techrotic_training_triumvirate.commands import (
    CommandParseError,
    parse_command_envelope,
)
from techrotic_training_triumvirate.evaluation.guard import frozen_evaluation_guard
from techrotic_training_triumvirate.schemas import (
    EpisodeRecord,
    JsonObject,
    JsonValue,
    TurnRecord,
    canonical_json,
    load_record,
)

from .model import (
    CorpusBuild,
    CorpusConfig,
    CorpusExample,
    CorpusIssue,
    CorpusShard,
    CorpusSource,
    CorpusSplit,
    CorpusTier,
    QuarantinedSource,
    TeacherEnrichment,
)

_EXTERNAL_SOURCE_CLASSES = frozenset(
    {
        "teacher-output",
        "third-party-dataset",
        "third-party-model-output",
        "game-derived-trace",
        "external",
    }
)
_ADMITTED_LICENSE_DISPOSITIONS = frozenset({"admitted", "compatible"})
_EXTERNAL_SOURCE_MARKERS = (
    "external",
    "third-party",
    "teacher",
    "model",
    "game-derived",
)


def _requires_license(source_class: str) -> bool:
    normalized = source_class.strip().lower()
    return normalized in _EXTERNAL_SOURCE_CLASSES or any(
        marker in normalized for marker in _EXTERNAL_SOURCE_MARKERS
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _count(values: Iterable[str]) -> JsonObject:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    result: JsonObject = {}
    for key in sorted(counts):
        result[key] = counts[key]
    return result


def _json_array_size(value: JsonValue | None) -> int:
    return len(value) if isinstance(value, list) else 0


def _json_string_list(values: Iterable[str]) -> list[JsonValue]:
    result: list[JsonValue] = []
    result.extend(values)
    return result


def _strings(value: JsonValue, *, prefix: str = "") -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    if isinstance(value, str):
        found.append((prefix, value))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_strings(item, prefix=f"{prefix}[{index}]"))
    elif isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else key
            found.extend(_strings(value[key], prefix=path))
    return tuple(found)


def _is_subset(claim: JsonValue, evidence: JsonValue) -> bool:
    if isinstance(claim, dict):
        if not isinstance(evidence, dict):
            return False
        return all(
            key in evidence and _is_subset(value, evidence[key])
            for key, value in claim.items()
        )
    if isinstance(claim, list):
        return claim == evidence
    return claim == evidence


def _fact_supported(claim: JsonObject, evidence: tuple[JsonObject, ...]) -> bool:
    return any(_is_subset(claim, candidate) for candidate in evidence)


def _episode_near_fingerprint(episode: EpisodeRecord) -> str:
    """Fingerprint semantics while ignoring volatile record and run identifiers."""

    turns: list[JsonValue] = []
    for turn in episode.turns:
        commands: list[JsonValue] = []
        for command in turn.assistant_action.commands:
            commands.append(
                {
                    "protocol_version": command.protocol_version,
                    "body": command.body,
                }
            )
        communications: list[JsonValue] = []
        for communication in turn.assistant_action.communications:
            communications.append(
                {
                    "channel": communication.channel,
                    "text": communication.text,
                    "recipients": list(communication.recipients),
                }
            )
        turns.append(
            {
                "observation": turn.observation.facts,
                "commands": commands,
                "communications": communications,
                "result_codes": [
                    {
                        "accepted": result.accepted,
                        "code": result.code,
                    }
                    for result in turn.interpreter_results
                ],
                "next_observation": turn.next_observation.facts,
            }
        )
    semantic: JsonObject = {
        "scenario_family": episode.scenario.identity.family,
        "generator": episode.scenario.identity.generator,
        "generator_version": episode.scenario.identity.generator_version,
        "seed": episode.scenario.identity.seed,
        "persona": {
            "archetype": episode.persona.archetype,
            "traits": episode.persona.traits,
            "speech_constraints": list(episode.persona.speech_constraints),
            "doctrine": episode.persona.doctrine,
            "tactical_biases": episode.persona.tactical_biases,
        },
        "turns": turns,
    }
    return _sha256_text(canonical_json(semantic))


def _provenance_issues(source: CorpusSource) -> list[CorpusIssue]:
    issues: list[CorpusIssue] = []
    if not source.provenance:
        return [
            CorpusIssue(
                "MISSING_PROVENANCE",
                "episode has no SourceProvenance records",
            )
        ]

    ids = [item.source_id for item in source.provenance]
    if len(ids) != len(set(ids)):
        issues.append(
            CorpusIssue(
                "DUPLICATE_PROVENANCE_ID",
                "source provenance IDs must be unique within an episode",
            )
        )

    for provenance in source.provenance:
        if not _requires_license(provenance.source_class):
            continue
        disposition = provenance.metadata.get("license_disposition")
        if (
            provenance.license_id is None
            or not provenance.license_id.strip()
            or disposition not in _ADMITTED_LICENSE_DISPOSITIONS
        ):
            issues.append(
                CorpusIssue(
                    "LICENSE_UNADMITTED",
                    (
                        f"{provenance.source_id} ({provenance.source_class}) lacks "
                        "an admitted license disposition"
                    ),
                )
            )
        if provenance.revision is None or provenance.source_content_hash is None:
            issues.append(
                CorpusIssue(
                    "PROVENANCE_INCOMPLETE",
                    (
                        f"{provenance.source_id} ({provenance.source_class}) lacks "
                        "revision or source content hash"
                    ),
                )
            )

    known_ids = set(ids)
    for enrichment in source.teacher_enrichments:
        if enrichment.source_id not in known_ids:
            issues.append(
                CorpusIssue(
                    "MISSING_TEACHER_PROVENANCE",
                    f"teacher enrichment source {enrichment.source_id!r} is unknown",
                )
            )

    if source.tier is CorpusTier.T2 and not source.teacher_enrichments:
        issues.append(
            CorpusIssue(
                "TIER_MISMATCH",
                "T2 requires at least one accepted teacher enrichment",
            )
        )
    if source.tier in {CorpusTier.T0, CorpusTier.T1} and source.teacher_enrichments:
        issues.append(
            CorpusIssue(
                "TIER_MISMATCH",
                f"{source.tier.value} cannot contain teacher enrichments",
            )
        )
    return issues


def _schema_protocol_issues(episode: EpisodeRecord) -> list[CorpusIssue]:
    issues: list[CorpusIssue] = []
    try:
        load_record(episode.to_dict(), expected_type=EpisodeRecord)
    except ValueError as exc:
        return [CorpusIssue("SCHEMA_INCOMPATIBLE", str(exc))]

    all_command_ids = [
        command.command_id
        for turn in episode.turns
        for command in turn.assistant_action.commands
    ]
    if len(all_command_ids) != len(set(all_command_ids)):
        issues.append(
            CorpusIssue(
                "DUPLICATE_COMMAND_ID",
                "command IDs must be unique across an episode",
            )
        )

    episode_command_ids = set(all_command_ids)
    for turn in episode.turns:
        command_ids = [command.command_id for command in turn.assistant_action.commands]
        result_ids = [result.command_id for result in turn.interpreter_results]
        if len(result_ids) != len(set(result_ids)):
            issues.append(
                CorpusIssue(
                    "DUPLICATE_RESULT",
                    f"turn {turn.turn_id} has duplicate interpreter results",
                )
            )
        if set(command_ids) != set(result_ids):
            issues.append(
                CorpusIssue(
                    "COMMAND_RESULT_MISMATCH",
                    (
                        f"turn {turn.turn_id} command/result IDs differ: "
                        f"{sorted(command_ids)!r} vs {sorted(result_ids)!r}"
                    ),
                )
            )
        for command in turn.assistant_action.commands:
            try:
                parse_command_envelope(command)
            except CommandParseError as exc:
                issues.append(
                    CorpusIssue(
                        "PROTOCOL_INCOMPATIBLE",
                        f"turn {turn.turn_id} command {command.command_id}: {exc}",
                    )
                )
        for result in turn.interpreter_results:
            if result.accepted and result.code != "OK":
                issues.append(
                    CorpusIssue(
                        "RESULT_INCONSISTENT",
                        (
                            f"accepted command {result.command_id} has non-OK "
                            f"code {result.code!r}"
                        ),
                    )
                )
            if not result.accepted and result.code == "OK":
                issues.append(
                    CorpusIssue(
                        "RESULT_INCONSISTENT",
                        f"rejected command {result.command_id} has OK code",
                    )
                )
        for event in turn.world_events:
            unknown = set(event.related_command_ids) - episode_command_ids
            if unknown:
                issues.append(
                    CorpusIssue(
                        "EVENT_COMMAND_MISMATCH",
                        (
                            f"event {event.event_id} refers to unknown commands "
                            f"{sorted(unknown)!r}"
                        ),
                    )
                )
    return issues


def _forbidden_target_values(episode: EpisodeRecord) -> dict[int, tuple[str, ...]]:
    result: dict[int, tuple[str, ...]] = {}
    global_forbidden = set(episode.initial_world.secret_ids)
    global_forbidden.update(episode.persona.secret_ids)
    for turn in episode.turns:
        forbidden = set(global_forbidden)
        for _, value in _strings(turn.annotations.evaluator_only):
            if value:
                forbidden.add(value)
        for path, value in _strings(turn.commander_private_context.beliefs):
            lowered = path.lower()
            if any(
                marker in lowered
                for marker in ("secret", "private", "hidden", "truth", "classified")
            ):
                forbidden.add(value)
        result[turn.turn_id] = tuple(sorted(forbidden))
    return result


def _visibility_issues(source: CorpusSource) -> list[CorpusIssue]:
    episode = source.episode
    issues: list[CorpusIssue] = []
    forbidden_by_turn = _forbidden_target_values(episode)
    for turn in episode.turns:
        target = canonical_json(turn.assistant_action.to_payload())
        leaked = tuple(
            value
            for value in forbidden_by_turn[turn.turn_id]
            if value and value in target
        )
        if leaked:
            issues.append(
                CorpusIssue(
                    "SECRET_LEAK",
                    (
                        f"turn {turn.turn_id} student target contains forbidden "
                        f"private or evaluator material: {leaked!r}"
                    ),
                )
            )

    for enrichment in source.teacher_enrichments:
        forbidden = forbidden_by_turn.get(enrichment.turn_id, ())
        surface = canonical_json(
            {
                "operational_facts": enrichment.operational_facts,
                "style_text": enrichment.style_text,
            }
        )
        leaked = tuple(value for value in forbidden if value and value in surface)
        if leaked:
            issues.append(
                CorpusIssue(
                    "SECRET_LEAK",
                    (
                        f"teacher enrichment {enrichment.source_id!r} contains "
                        f"forbidden private or evaluator material: {leaked!r}"
                    ),
                )
            )
    return issues


def _teacher_issues(source: CorpusSource) -> list[CorpusIssue]:
    issues: list[CorpusIssue] = []
    turns = {turn.turn_id: turn for turn in source.episode.turns}
    for enrichment in source.teacher_enrichments:
        turn = turns.get(enrichment.turn_id)
        if turn is None:
            issues.append(
                CorpusIssue(
                    "TEACHER_TURN_UNKNOWN",
                    f"teacher enrichment refers to missing turn {enrichment.turn_id}",
                )
            )
            continue
        evidence: tuple[JsonObject, ...] = (
            turn.observation.facts,
            turn.next_observation.facts,
            *(result.detail for result in turn.interpreter_results),
            *(event.data for event in turn.world_events),
        )
        if enrichment.operational_facts and not _fact_supported(
            enrichment.operational_facts,
            evidence,
        ):
            issues.append(
                CorpusIssue(
                    "UNSUPPORTED_TEACHER_FACT",
                    (
                        f"teacher enrichment {enrichment.source_id!r} on turn "
                        f"{turn.turn_id} asserts unsupported operational facts"
                    ),
                )
            )
    return issues


def _recovery_issues(source: CorpusSource) -> list[CorpusIssue]:
    issues: list[CorpusIssue] = []
    prior_rejected: set[str] = set()
    saw_recovery = False
    for turn in source.episode.turns:
        label = turn.annotations.labels.get("recovery_of_command_id")
        if label is not None:
            saw_recovery = True
            if not isinstance(label, str) or not label:
                issues.append(
                    CorpusIssue(
                        "RECOVERY_MALFORMED",
                        f"turn {turn.turn_id} recovery_of_command_id must be a string",
                    )
                )
            elif label not in prior_rejected:
                issues.append(
                    CorpusIssue(
                        "RECOVERY_MALFORMED",
                        (
                            f"turn {turn.turn_id} does not follow rejected command "
                            f"{label!r}"
                        ),
                    )
                )
            if not turn.assistant_action.commands:
                issues.append(
                    CorpusIssue(
                        "RECOVERY_MALFORMED",
                        f"turn {turn.turn_id} recovery has no corrective command",
                    )
                )
        prior_rejected = {
            result.command_id
            for result in turn.interpreter_results
            if not result.accepted
        }

    if source.tier is CorpusTier.T3 and not saw_recovery:
        has_rejection_then_followup = any(
            any(not result.accepted for result in previous.interpreter_results)
            for previous in source.episode.turns[:-1]
        )
        if not has_rejection_then_followup:
            issues.append(
                CorpusIssue(
                    "TIER_MISMATCH",
                    "T3 requires student-visited rejection or correction evidence",
                )
            )
    return issues


def validate_source(source: CorpusSource) -> tuple[CorpusIssue, ...]:
    """Run all admission validators for one candidate corpus source."""

    issues = [
        *_provenance_issues(source),
        *_schema_protocol_issues(source.episode),
        *_visibility_issues(source),
        *_teacher_issues(source),
        *_recovery_issues(source),
    ]
    unique: dict[tuple[str, str], CorpusIssue] = {}
    for issue in issues:
        unique[(issue.code, issue.detail)] = issue
    return tuple(unique[key] for key in sorted(unique))


def _split_for(source: CorpusSource, config: CorpusConfig) -> CorpusSplit:
    identity = source.episode.scenario.identity
    guard = frozen_evaluation_guard()
    if (
        guard.is_reserved(family=identity.family, seed=identity.seed)
        or identity.scenario_id in config.frozen_scenario_ids
        or identity.family in config.frozen_families
    ):
        return CorpusSplit.FROZEN_EVAL
    digest = hashlib.sha256(f"{config.seed}:{identity.family}".encode()).digest()
    bucket = int.from_bytes(digest[:8], "big") % 100
    if bucket < config.dev_percent:
        return CorpusSplit.DEV
    return CorpusSplit.TRAIN


def _teacher_by_turn(source: CorpusSource) -> dict[int, tuple[TeacherEnrichment, ...]]:
    result: dict[int, list[TeacherEnrichment]] = {}
    for enrichment in source.teacher_enrichments:
        result.setdefault(enrichment.turn_id, []).append(enrichment)
    return {
        turn_id: tuple(
            sorted(
                items,
                key=lambda item: (
                    item.source_id,
                    canonical_json(item.operational_facts),
                ),
            )
        )
        for turn_id, items in result.items()
    }


def _examples_for(
    source: CorpusSource,
    split: CorpusSplit,
) -> tuple[CorpusExample, ...]:
    episode = source.episode
    enrichments = _teacher_by_turn(source)
    examples: list[CorpusExample] = []
    previous: TurnRecord | None = None
    for turn in episode.turns:
        rejected = tuple(
            result for result in turn.interpreter_results if not result.accepted
        )
        if rejected:
            previous = turn
            continue

        input_object: JsonObject = {
            "observation": turn.observation.to_dict(),
            "commander_private_context": turn.commander_private_context.to_dict(),
            "persona": episode.persona.to_dict(),
        }
        mode = "standard"
        if previous is not None:
            prior_rejected = tuple(
                result for result in previous.interpreter_results if not result.accepted
            )
            if prior_rejected:
                mode = "recovery"
                input_object["prior_failure"] = {
                    "assistant_action": previous.assistant_action.to_dict(),
                    "interpreter_results": [
                        result.to_dict() for result in prior_rejected
                    ],
                    "world_events": [
                        event.to_dict() for event in previous.world_events
                    ],
                }

        turn_enrichments = enrichments.get(turn.turn_id, ())
        if turn_enrichments:
            input_object["teacher_enrichment"] = [
                {
                    "source_id": item.source_id,
                    "style_text": item.style_text,
                    "operational_facts": item.operational_facts,
                }
                for item in turn_enrichments
            ]

        target = turn.assistant_action.to_payload()
        identity_base: JsonObject = {
            "episode_hash": episode.content_hash(),
            "turn_id": turn.turn_id,
            "mode": mode,
            "input": input_object,
            "target": target,
            "tier": source.tier.value,
        }
        example_id = _sha256_text(canonical_json(identity_base))
        examples.append(
            CorpusExample(
                example_id=example_id,
                split=split,
                tier=source.tier,
                episode_id=episode.episode_id,
                scenario_id=episode.scenario.identity.scenario_id,
                scenario_family=episode.scenario.identity.family,
                persona_id=episode.persona.persona_id,
                turn_id=turn.turn_id,
                mode=mode,
                input=input_object,
                target=target,
                provenance_refs=tuple(
                    sorted(item.source_id for item in source.provenance)
                ),
                teacher_source_ids=tuple(
                    sorted(item.source_id for item in turn_enrichments)
                ),
            )
        )
        previous = turn
    return tuple(examples)


def _make_shards(
    examples: tuple[CorpusExample, ...],
    config: CorpusConfig,
) -> tuple[CorpusShard, ...]:
    shards: list[CorpusShard] = []
    for split in CorpusSplit:
        selected = sorted(
            (example for example in examples if example.split is split),
            key=lambda item: (
                item.scenario_family,
                item.scenario_id,
                item.episode_id,
                item.turn_id,
                item.example_id,
            ),
        )
        for index in range(0, len(selected), config.shard_size):
            chunk = selected[index : index + config.shard_size]
            shard_index = index // config.shard_size
            content = "".join(
                f"{canonical_json(example.to_object())}\n" for example in chunk
            )
            name = f"{split.value}-{shard_index:05d}.jsonl"
            shards.append(
                CorpusShard(
                    name=name,
                    split=split,
                    line_count=len(chunk),
                    sha256=_sha256_text(content),
                    content=content,
                )
            )
    return tuple(shards)


def _manifest(
    examples: tuple[CorpusExample, ...],
    shards: tuple[CorpusShard, ...],
    quarantine: tuple[QuarantinedSource, ...],
    admitted_sources: tuple[CorpusSource, ...],
    config: CorpusConfig,
) -> JsonObject:
    split_membership: dict[CorpusSplit, list[str]] = {
        split: [] for split in CorpusSplit
    }
    for source in admitted_sources:
        split = _split_for(source, config)
        identity = source.episode.scenario.identity
        split_membership[split].append(
            canonical_json(
                {
                    "episode_hash": source.episode.content_hash(),
                    "scenario_id": identity.scenario_id,
                    "family": identity.family,
                }
            )
        )

    split_identity: JsonObject = {}
    for split in CorpusSplit:
        members = sorted(split_membership[split])
        split_identity[split.value] = _sha256_text(canonical_json(members))

    rejection_codes = [issue.code for item in quarantine for issue in item.issues]
    error_codes = [
        result.code
        for source in admitted_sources
        for turn in source.episode.turns
        for result in turn.interpreter_results
        if not result.accepted
    ]
    teacher_example_count = sum(bool(item.teacher_source_ids) for item in examples)
    command_count = sum(
        _json_array_size(item.target.get("commands")) for item in examples
    )
    communication_count = sum(
        _json_array_size(item.target.get("communications")) for item in examples
    )
    examples_with_commands = sum(bool(item.target.get("commands")) for item in examples)
    examples_with_communications = sum(
        bool(item.target.get("communications")) for item in examples
    )
    teacher_source_ids = {
        enrichment.source_id
        for source in admitted_sources
        for enrichment in source.teacher_enrichments
    }

    guard = frozen_evaluation_guard()
    manifest: JsonObject = {
        "manifest_version": 1,
        "config": {
            "seed": config.seed,
            "dev_percent": config.dev_percent,
            "shard_size": config.shard_size,
            "frozen_scenario_ids": _json_string_list(
                sorted(config.frozen_scenario_ids)
            ),
            "frozen_families": _json_string_list(sorted(config.frozen_families)),
            "frozen_evaluation_guard": {
                "benchmark_id": guard.benchmark_id,
                "benchmark_version": guard.benchmark_version,
                "benchmark_hash": guard.benchmark_hash,
            },
        },
        "counts": {
            "admitted_episodes": len(admitted_sources),
            "quarantined_episodes": len(quarantine),
            "examples": len(examples),
        },
        "tier_composition": _count(item.tier.value for item in examples),
        "world_distribution": _count(item.scenario_family for item in examples),
        "persona_distribution": _count(item.persona_id for item in examples),
        "error_distribution": _count(error_codes),
        "teacher_contribution": {
            "examples": teacher_example_count,
            "source_count": len(teacher_source_ids),
        },
        "content_composition": {
            "command_count": command_count,
            "communication_count": communication_count,
            "examples_with_commands": examples_with_commands,
            "examples_with_communications": examples_with_communications,
            "teacher_enriched_examples": teacher_example_count,
        },
        "rejection_reasons": _count(rejection_codes),
        "split_distribution": _count(item.split.value for item in examples),
        "split_identity": split_identity,
        "shards": [
            {
                "name": shard.name,
                "split": shard.split.value,
                "line_count": shard.line_count,
                "sha256": shard.sha256,
            }
            for shard in shards
        ],
    }
    return manifest


def assemble_corpus(
    sources: Iterable[CorpusSource],
    *,
    config: CorpusConfig | None = None,
) -> CorpusBuild:
    """Validate, deduplicate, split, and assemble a deterministic corpus."""

    resolved_config = config or CorpusConfig()
    ordered_sources = sorted(
        tuple(sources),
        key=lambda item: (
            item.episode.scenario.identity.family,
            item.episode.scenario.identity.scenario_id,
            item.episode.episode_id,
            item.episode.content_hash(),
        ),
    )

    quarantine: list[QuarantinedSource] = []
    admitted: list[CorpusSource] = []
    exact_seen: dict[str, str] = {}
    near_seen: dict[str, str] = {}

    for source in ordered_sources:
        issues = list(validate_source(source))
        exact = source.episode.content_hash()
        near = _episode_near_fingerprint(source.episode)
        if exact in exact_seen:
            issues.append(
                CorpusIssue(
                    "DUPLICATE_EPISODE",
                    (
                        f"exact duplicate of episode {exact_seen[exact]!r}; "
                        "duplicates cannot cross corpus partitions"
                    ),
                )
            )
        elif near in near_seen:
            issues.append(
                CorpusIssue(
                    "NEAR_DUPLICATE_EPISODE",
                    (
                        f"near-exact duplicate of episode {near_seen[near]!r}; "
                        "volatile identifiers do not make a new record"
                    ),
                )
            )

        if issues:
            unique = {(item.code, item.detail): item for item in issues}
            quarantine.append(
                QuarantinedSource(
                    episode_id=source.episode.episode_id,
                    issues=tuple(unique[key] for key in sorted(unique)),
                )
            )
            continue

        exact_seen[exact] = source.episode.episode_id
        near_seen[near] = source.episode.episode_id
        admitted.append(source)

    examples = tuple(
        example
        for source in admitted
        for example in _examples_for(source, _split_for(source, resolved_config))
    )
    examples = tuple(
        sorted(
            examples,
            key=lambda item: (
                item.split.value,
                item.scenario_family,
                item.scenario_id,
                item.episode_id,
                item.turn_id,
                item.example_id,
            ),
        )
    )
    shards = _make_shards(examples, resolved_config)
    quarantined = tuple(sorted(quarantine, key=lambda item: item.episode_id))
    admitted_sources = tuple(admitted)
    manifest = _manifest(
        examples,
        shards,
        quarantined,
        admitted_sources,
        resolved_config,
    )
    return CorpusBuild(
        examples=examples,
        shards=shards,
        quarantine=quarantined,
        manifest=manifest,
    )


def write_corpus(build: CorpusBuild, output_dir: str | Path) -> tuple[Path, ...]:
    """Write deterministic JSONL shards plus canonical manifest JSON."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for shard in build.shards:
        path = root / shard.name
        path.write_text(shard.content, encoding="utf-8", newline="\n")
        written.append(path)

    quarantine_object: list[JsonValue] = [
        {
            "episode_id": item.episode_id,
            "issues": [
                {"code": issue.code, "detail": issue.detail} for issue in item.issues
            ],
        }
        for item in build.quarantine
    ]
    quarantine_path = root / "quarantine.json"
    quarantine_path.write_text(
        f"{canonical_json(quarantine_object)}\n",
        encoding="utf-8",
        newline="\n",
    )
    written.append(quarantine_path)

    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        f"{canonical_json(build.manifest)}\n",
        encoding="utf-8",
        newline="\n",
    )
    written.append(manifest_path)
    return tuple(written)
