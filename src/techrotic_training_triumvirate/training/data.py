"""Leak-safe corpus mapping and exact dataset identity for TTT-012."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.corpus import CorpusExample
from techrotic_training_triumvirate.schemas import JsonObject, JsonValue, canonical_json

from .model import (
    ChatMessage,
    DatasetIdentity,
    MappedExample,
    SourceExample,
    TrainingMix,
)

_SYSTEM_PROMPT = (
    "You are a TTT Student Commander. Use only admitted observations and private "
    "commander context. Emit only the requested TTT assistant action: typed commands "
    "and allowed communications. Environment results are authoritative inputs, never "
    "assistant-authored outcomes."
)
_FORBIDDEN_TARGET_KEYS = frozenset(
    {
        "interpreter_results",
        "world_events",
        "next_observation",
        "player_observation",
        "player_intercepts",
        "annotations",
        "evaluation_annotations",
    }
)
_FORBIDDEN_TARGET_SCHEMAS = frozenset(
    {
        "ttt.interpreter_result",
        "ttt.authoritative_event",
        "ttt.commander_observation",
        "ttt.player_observation",
        "ttt.evaluation_annotations",
    }
)


class TrainingDataError(ValueError):
    """Raised when a corpus cannot safely become a supervised training view."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contains_forbidden_target(value: JsonValue) -> bool:
    if isinstance(value, list):
        return any(_contains_forbidden_target(item) for item in value)
    if isinstance(value, dict):
        schema = value.get("schema")
        if isinstance(schema, str) and schema in _FORBIDDEN_TARGET_SCHEMAS:
            return True
        if any(key in _FORBIDDEN_TARGET_KEYS for key in value):
            return True
        return any(_contains_forbidden_target(item) for item in value.values())
    return False


def validate_assistant_target(target: JsonObject) -> None:
    """Enforce that supervised loss can cover only student emissions."""

    if set(target) != {"commands", "communications"}:
        raise TrainingDataError(
            "assistant target must contain exactly commands and communications"
        )
    if not isinstance(target["commands"], list) or not isinstance(
        target["communications"], list
    ):
        raise TrainingDataError("commands and communications must be arrays")
    if _contains_forbidden_target(target):
        raise TrainingDataError(
            "authoritative environment/evaluation records are forbidden in targets"
        )


def source_example_from_corpus(example: CorpusExample) -> SourceExample:
    """Project an already-admitted corpus example into the training layer."""

    return SourceExample(
        example_id=example.example_id,
        split=example.split.value,
        tier=example.tier.value,
        mode=example.mode,
        input=copy.deepcopy(example.input),
        target=copy.deepcopy(example.target),
    )


def _mixed_target(
    source: SourceExample,
    mix: TrainingMix,
) -> JsonObject | None:
    validate_assistant_target(source.target)
    target = copy.deepcopy(source.target)

    if mix is TrainingMix.OPERATIONAL:
        target["communications"] = []
    elif mix is TrainingMix.PERSONA:
        target["commands"] = []
    elif mix is TrainingMix.JOINT and source.mode == "recovery":
        return None

    commands = cast(list[JsonValue], target["commands"])
    communications = cast(list[JsonValue], target["communications"])
    if not commands and not communications:
        return None
    return target


def map_source_example(
    source: SourceExample,
    *,
    mix: TrainingMix,
) -> MappedExample | None:
    """Map one corpus example to semantic chat + assistant-only target."""

    if source.split == "frozen_eval":
        return None
    target = _mixed_target(source, mix)
    if target is None:
        return None

    user_payload: JsonObject = {
        "mode": source.mode,
        "tier": source.tier,
        "input": source.input,
    }
    return MappedExample(
        example_id=source.example_id,
        split=source.split,
        tier=source.tier,
        mode=source.mode,
        prompt_messages=(
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=canonical_json(user_payload)),
        ),
        assistant_target=canonical_json(target),
    )


def map_dataset(
    sources: tuple[SourceExample, ...],
    *,
    mix: TrainingMix,
) -> tuple[MappedExample, ...]:
    """Map an admitted corpus deterministically, excluding frozen evaluation."""

    mapped = tuple(
        item
        for source in sources
        if (item := map_source_example(source, mix=mix)) is not None
    )
    return tuple(sorted(mapped, key=lambda item: item.example_id))


def dataset_identity_from_examples(
    sources: tuple[SourceExample, ...],
    *,
    manifest_sha256: str | None = None,
    shard_hashes: tuple[tuple[str, str], ...] = (),
    split_identity: JsonObject | None = None,
) -> DatasetIdentity:
    """Build deterministic identity for an in-memory/smoke corpus."""

    objects = [source.to_object() for source in sorted(sources, key=lambda item: item.example_id)]
    dataset_hash = _sha256_text(canonical_json(objects))
    return DatasetIdentity(
        manifest_sha256=manifest_sha256 or dataset_hash,
        dataset_hash=dataset_hash,
        shard_hashes=tuple(sorted(shard_hashes)),
        split_identity=copy.deepcopy(split_identity or {}),
    )


def _source_from_object(raw: object) -> SourceExample:
    if not isinstance(raw, dict):
        raise TrainingDataError("corpus JSONL line must be an object")
    data = cast(dict[str, Any], raw)
    required = {"example_id", "split", "tier", "mode", "input", "target"}
    missing = required - set(data)
    if missing:
        raise TrainingDataError(f"corpus example missing fields: {sorted(missing)!r}")
    if not isinstance(data["input"], dict) or not isinstance(data["target"], dict):
        raise TrainingDataError("corpus input/target must be objects")
    return SourceExample(
        example_id=str(data["example_id"]),
        split=str(data["split"]),
        tier=str(data["tier"]),
        mode=str(data["mode"]),
        input=cast(JsonObject, data["input"]),
        target=cast(JsonObject, data["target"]),
    )


def load_corpus_examples(
    corpus_dir: str | Path,
) -> tuple[tuple[SourceExample, ...], DatasetIdentity]:
    """Verify a TTT-007 corpus manifest/shards and load train/dev examples only."""

    root = Path(corpus_dir)
    manifest_path = root / "manifest.json"
    raw_manifest = manifest_path.read_text(encoding="utf-8")
    manifest_sha = _sha256_text(raw_manifest)
    parsed: object = json.loads(raw_manifest)
    if not isinstance(parsed, dict):
        raise TrainingDataError("corpus manifest must be an object")
    manifest = cast(dict[str, Any], parsed)
    shards = manifest.get("shards")
    if not isinstance(shards, list):
        raise TrainingDataError("corpus manifest has no shard list")

    examples: list[SourceExample] = []
    shard_hashes: list[tuple[str, str]] = []
    for raw_shard in shards:
        if not isinstance(raw_shard, dict):
            raise TrainingDataError("shard manifest entry must be an object")
        shard = cast(dict[str, Any], raw_shard)
        name = shard.get("name")
        expected = shard.get("sha256")
        split = shard.get("split")
        if not isinstance(name, str) or Path(name).name != name:
            raise TrainingDataError("unsafe or invalid shard name")
        if not isinstance(expected, str):
            raise TrainingDataError(f"{name} has no SHA-256")
        shard_path = root / name
        content = shard_path.read_text(encoding="utf-8")
        actual = _sha256_text(content)
        if actual != expected:
            raise TrainingDataError(f"{name} SHA-256 mismatch")
        shard_hashes.append((name, actual))

        if split == "frozen_eval":
            continue
        if split not in {"train", "dev"}:
            raise TrainingDataError(f"{name} has unsupported split {split!r}")
        for line in content.splitlines():
            if not line:
                continue
            source = _source_from_object(json.loads(line))
            if source.split != split:
                raise TrainingDataError(
                    f"{name} contains {source.split!r} example in {split!r} shard"
                )
            examples.append(source)

    if len({item.example_id for item in examples}) != len(examples):
        raise TrainingDataError("duplicate example_id in training-visible shards")

    split_identity = manifest.get("split_identity", {})
    if not isinstance(split_identity, dict):
        raise TrainingDataError("manifest split_identity must be an object")
    sources = tuple(sorted(examples, key=lambda item: item.example_id))
    identity = dataset_identity_from_examples(
        sources,
        manifest_sha256=manifest_sha,
        shard_hashes=tuple(shard_hashes),
        split_identity=cast(JsonObject, split_identity),
    )
    return sources, identity


def _command(command_id: str, unit_id: str) -> JsonObject:
    return {
        "schema": "ttt.command_envelope",
        "schema_version": 1,
        "payload": {
            "command_id": command_id,
            "protocol_version": "ttt-command-v1",
            "body": {"op": "hold", "unit_id": unit_id},
        },
    }


def _communication(text: str) -> JsonObject:
    return {
        "schema": "ttt.communication",
        "schema_version": 1,
        "payload": {"channel": "squad", "text": text, "recipients": []},
    }


def smoke_source_examples() -> tuple[SourceExample, ...]:
    """Small local fixtures exercising ordinary/persona/recovery mapping."""

    base_input: JsonObject = {
        "observation": {
            "schema": "ttt.commander_observation",
            "schema_version": 1,
            "payload": {"turn_id": 0, "facts": {"visible_unit": "u-1"}},
        },
        "commander_private_context": {
            "schema": "ttt.commander_private_context",
            "schema_version": 1,
            "payload": {"goals": ["hold"], "beliefs": {}, "secret_refs": [], "memory_refs": []},
        },
        "persona": {
            "schema": "ttt.persona",
            "schema_version": 1,
            "payload": {
                "persona_id": "smoke-persona",
                "archetype": "measured",
                "traits": {"tempo": "calm"},
                "speech_constraints": [],
                "doctrine": {},
                "tactical_biases": {},
            },
        },
    }
    recovery_input = copy.deepcopy(base_input)
    recovery_input["prior_failure"] = {
        "assistant_action": {
            "commands": [_command("failed-1", "u-9")],
            "communications": [],
        },
        "interpreter_results": [
            {
                "schema": "ttt.interpreter_result",
                "schema_version": 1,
                "payload": {
                    "command_id": "failed-1",
                    "accepted": False,
                    "code": "UNKNOWN_ENTITY",
                    "detail": {},
                },
            }
        ],
        "world_events": [],
    }

    return (
        SourceExample(
            example_id="smoke-001",
            split="train",
            tier="T1",
            mode="standard",
            input=copy.deepcopy(base_input),
            target={
                "commands": [_command("cmd-001", "u-1")],
                "communications": [],
            },
        ),
        SourceExample(
            example_id="smoke-002",
            split="train",
            tier="T2",
            mode="standard",
            input=copy.deepcopy(base_input),
            target={
                "commands": [],
                "communications": [_communication("Hold steady; let them spend first.")],
            },
        ),
        SourceExample(
            example_id="smoke-003",
            split="dev",
            tier="T2",
            mode="standard",
            input=copy.deepcopy(base_input),
            target={
                "commands": [_command("cmd-003", "u-1")],
                "communications": [_communication("Anchor here.")],
            },
        ),
        SourceExample(
            example_id="smoke-004",
            split="train",
            tier="T3",
            mode="recovery",
            input=recovery_input,
            target={
                "commands": [_command("cmd-004", "u-1")],
                "communications": [_communication("Correction: holding the visible unit.")],
            },
        ),
    )
