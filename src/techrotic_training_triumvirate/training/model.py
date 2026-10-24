"""Stable records for TTT-012 training, export, and parity."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from techrotic_training_triumvirate.schemas import JsonObject


class TrainingMix(str, Enum):
    """Supported supervised corpus mixtures."""

    OPERATIONAL = "operational"
    PERSONA = "persona"
    JOINT = "joint"
    JOINT_CORRECTIVE = "joint+corrective"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One semantic chat message before model-native template rendering."""

    role: str
    content: str

    def to_object(self) -> JsonObject:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class SourceExample:
    """Training-facing subset of one validated TTT corpus example."""

    example_id: str
    split: str
    tier: str
    mode: str
    input: JsonObject
    target: JsonObject

    def to_object(self) -> JsonObject:
        return {
            "example_id": self.example_id,
            "split": self.split,
            "tier": self.tier,
            "mode": self.mode,
            "input": self.input,
            "target": self.target,
        }


@dataclass(frozen=True, slots=True)
class MappedExample:
    """One supervised sequence with an explicit assistant-only loss target."""

    example_id: str
    split: str
    tier: str
    mode: str
    prompt_messages: tuple[ChatMessage, ...]
    assistant_target: str

    def to_object(self) -> JsonObject:
        return {
            "example_id": self.example_id,
            "split": self.split,
            "tier": self.tier,
            "mode": self.mode,
            "prompt_messages": [item.to_object() for item in self.prompt_messages],
            "assistant_target": self.assistant_target,
        }


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    """Exact corpus manifest/shard identity bound into a training run."""

    manifest_sha256: str
    dataset_hash: str
    shard_hashes: tuple[tuple[str, str], ...]
    split_identity: JsonObject

    def to_object(self) -> JsonObject:
        return {
            "manifest_sha256": self.manifest_sha256,
            "dataset_hash": self.dataset_hash,
            "shard_hashes": {name: digest for name, digest in self.shard_hashes},
            "split_identity": self.split_identity,
        }


@dataclass(frozen=True, slots=True)
class ModelBinding:
    """One admitted student resolved from the TTT-011 model cast."""

    model_key: str
    role: str
    native_repository: str
    native_revision: str
    native_artifact_names: tuple[str, ...]
    native_artifact_sha256: str | None
    tokenizer_chat_format: str
    model_cast_sha256: str

    def to_object(self) -> JsonObject:
        return {
            "model_key": self.model_key,
            "role": self.role,
            "native_repository": self.native_repository,
            "native_revision": self.native_revision,
            "native_artifact_names": list(self.native_artifact_names),
            "native_artifact_sha256": self.native_artifact_sha256,
            "tokenizer_chat_format": self.tokenizer_chat_format,
            "model_cast_sha256": self.model_cast_sha256,
        }


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    """Resolved fine-tuning configuration for one admitted student."""

    profile_version: int
    model_key: str
    backend: str
    method: str
    template_strategy: str
    mix: TrainingMix
    seed: int
    max_sequence_tokens: int
    learning_rate: float
    epochs: int
    micro_batch_size: int
    gradient_accumulation_steps: int
    save_steps: int
    lora_rank: int
    lora_alpha: int
    lora_dropout: float
    lora_target_modules: tuple[str, ...]
    parity_max_new_tokens: int

    def to_object(self) -> JsonObject:
        return {
            "profile_version": self.profile_version,
            "model_key": self.model_key,
            "backend": self.backend,
            "method": self.method,
            "template_strategy": self.template_strategy,
            "mix": self.mix.value,
            "seed": self.seed,
            "max_sequence_tokens": self.max_sequence_tokens,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "micro_batch_size": self.micro_batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "save_steps": self.save_steps,
            "lora": {
                "rank": self.lora_rank,
                "alpha": self.lora_alpha,
                "dropout": self.lora_dropout,
                "target_modules": list(self.lora_target_modules),
            },
            "parity_max_new_tokens": self.parity_max_new_tokens,
        }


@dataclass(frozen=True, slots=True)
class BudgetAuthorization:
    """Explicit heavy-training admission for one invocation."""

    gpu_hours: float
    external_compute_cost_gbp: float
    paid_model_api_cost_gbp: float

    def to_object(self) -> JsonObject:
        return {
            "gpu_hours": self.gpu_hours,
            "external_compute_cost_gbp": self.external_compute_cost_gbp,
            "paid_model_api_cost_gbp": self.paid_model_api_cost_gbp,
        }


@dataclass(frozen=True, slots=True)
class TinyTrainingResult:
    """Deterministic tiny-backend result used by default CI smoke training."""

    training_identity: str
    ordered_example_ids: tuple[str, ...]
    completed_steps: int
    complete: bool
    memory: dict[str, str]
    model_hash: str

    def to_object(self) -> JsonObject:
        return {
            "training_identity": self.training_identity,
            "ordered_example_ids": list(self.ordered_example_ids),
            "completed_steps": self.completed_steps,
            "complete": self.complete,
            "memory": dict(self.memory),
            "model_hash": self.model_hash,
        }
