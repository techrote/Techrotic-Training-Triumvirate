"""Deterministic tiny training/checkpoint backend for default CI."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.schemas import JsonObject, canonical_json

from .model import (
    DatasetIdentity,
    MappedExample,
    ModelBinding,
    TinyTrainingResult,
    TrainingConfig,
)


class TinyTrainingError(ValueError):
    """Raised when smoke-training state cannot be resumed safely."""


def render_prompt(example: MappedExample) -> str:
    """Canonical prompt identity before any model-native tokenizer template."""

    return canonical_json([item.to_object() for item in example.prompt_messages])


def _prompt_hash(example: MappedExample) -> str:
    return hashlib.sha256(render_prompt(example).encode()).hexdigest()


def _training_identity(
    train_examples: tuple[MappedExample, ...],
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
) -> str:
    payload: JsonObject = {
        "smoke_backend": "tiny-deterministic-v1",
        "model_binding": binding.to_object(),
        "training_config": config.to_object(),
        "dataset_identity": dataset.to_object(),
        "training_example_ids": [item.example_id for item in train_examples],
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def train_tiny(
    mapped: tuple[MappedExample, ...],
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    checkpoint_path: str | Path,
    resume: bool = False,
    max_steps: int | None = None,
) -> TinyTrainingResult:
    """Train an exact-match tiny model with seeded order and strict resume identity."""

    train_examples = tuple(item for item in mapped if item.split == "train")
    if not train_examples:
        raise TinyTrainingError("smoke training requires training-split examples")

    identity = _training_identity(
        train_examples,
        binding=binding,
        config=config,
        dataset=dataset,
    )
    order = list(range(len(train_examples)))
    random.Random(config.seed).shuffle(order)
    order_ids = tuple(train_examples[index].example_id for index in order)
    checkpoint = Path(checkpoint_path)

    memory: dict[str, str] = {}
    completed_steps = 0
    if resume:
        if not checkpoint.is_file():
            raise TinyTrainingError("resume checkpoint does not exist")
        parsed: object = json.loads(checkpoint.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise TinyTrainingError("resume checkpoint is malformed")
        state = cast(dict[str, Any], parsed)
        if state.get("training_identity") != identity:
            raise TinyTrainingError("resume checkpoint training identity mismatch")
        if tuple(state.get("ordered_example_ids", ())) != order_ids:
            raise TinyTrainingError("resume checkpoint example order mismatch")
        raw_memory = state.get("memory")
        if not isinstance(raw_memory, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_memory.items()
        ):
            raise TinyTrainingError("resume checkpoint model state is malformed")
        memory = dict(cast(dict[str, str], raw_memory))
        completed_steps = int(state.get("completed_steps", 0))
        if not 0 <= completed_steps <= len(order):
            raise TinyTrainingError("resume checkpoint step is out of range")

    stop = len(order) if max_steps is None else min(max_steps, len(order))
    if stop < completed_steps:
        raise TinyTrainingError("max_steps precedes the resumed checkpoint")

    for position in range(completed_steps, stop):
        example = train_examples[order[position]]
        memory[_prompt_hash(example)] = example.assistant_target

    completed_steps = stop
    complete = completed_steps == len(order)
    model_hash = hashlib.sha256(canonical_json(memory).encode()).hexdigest()
    memory_object: JsonObject = {key: value for key, value in memory.items()}
    state_object: JsonObject = {
        "schema_version": 1,
        "backend": "tiny-deterministic-v1",
        "training_identity": identity,
        "ordered_example_ids": list(order_ids),
        "completed_steps": completed_steps,
        "complete": complete,
        "memory": memory_object,
        "model_hash": model_hash,
    }
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        f"{canonical_json(state_object)}\n",
        encoding="utf-8",
        newline="\n",
    )
    return TinyTrainingResult(
        training_identity=identity,
        ordered_example_ids=order_ids,
        completed_steps=completed_steps,
        complete=complete,
        memory=memory,
        model_hash=model_hash,
    )


def predict_tiny(result: TinyTrainingResult, example: MappedExample) -> str:
    """Return the learned assistant target for a fixed smoke fixture."""

    return result.memory.get(_prompt_hash(example), "")
