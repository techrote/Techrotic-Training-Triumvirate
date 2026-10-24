"""Resolve TTT-012 training plans from the admitted TTT-011 cast."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from typing import Any, cast

from techrotic_training_triumvirate.model_admission import (
    load_model_cast_v1,
    model_cast_content_hash,
    validate_model_cast_v1,
)
from techrotic_training_triumvirate.schemas import JsonObject, canonical_json

from .model import BudgetAuthorization, ModelBinding, TrainingConfig, TrainingMix


class TrainingAdmissionError(ValueError):
    """Raised when a training request violates an admission or budget contract."""


def _load_profiles(profile_version: int = 1) -> dict[str, Any]:
    if type(profile_version) is not int or profile_version not in {1, 2}:
        raise TrainingAdmissionError("unsupported training profile version")
    raw = (
        files("techrotic_training_triumvirate.training")
        / f"profiles_v{profile_version}.json"
    ).read_text(encoding="utf-8")
    parsed: object = json.loads(raw)
    if not isinstance(parsed, dict):
        raise TrainingAdmissionError("training profiles must be a JSON object")
    return cast(dict[str, Any], parsed)


def _student_key(selector: str) -> tuple[str, str]:
    cast_data = load_model_cast_v1()
    validate_model_cast_v1(cast_data)
    roles = cast(dict[str, Any], cast_data["roles"])
    models = cast(dict[str, Any], cast_data["models"])

    normalized = selector.strip().lower()
    if normalized in {"primary", "primary_compact_student"}:
        key = cast(str, roles["primary_compact_student"])
        return key, "primary_compact_student"
    if normalized in {"challenger", "challenger_student"}:
        challengers = cast(list[str], roles["challenger_students"])
        if not challengers:
            raise TrainingAdmissionError("no challenger student is admitted")
        return challengers[0], "challenger_student"
    if selector not in models:
        raise TrainingAdmissionError(f"unknown admitted model {selector!r}")

    record = cast(dict[str, Any], models[selector])
    record_roles = cast(list[str], record["roles"])
    if "primary_compact_student" in record_roles:
        return selector, "primary_compact_student"
    if "challenger_student" in record_roles:
        return selector, "challenger_student"
    raise TrainingAdmissionError(f"{selector!r} is not admitted as a student")


def resolve_model_binding(selector: str = "primary") -> ModelBinding:
    """Resolve immutable native training identity from model-cast admission."""

    cast_data = load_model_cast_v1()
    validate_model_cast_v1(cast_data)
    key, role = _student_key(selector)
    models = cast(dict[str, Any], cast_data["models"])
    record = cast(dict[str, Any], models[key])
    native = cast(dict[str, Any], record["native"])

    repository = native.get("repository")
    if not isinstance(repository, str) or not repository:
        raise TrainingAdmissionError(f"{key} native repository is missing")

    revision_value = native.get("revision", native.get("artifact_commit"))
    if not isinstance(revision_value, str) or not revision_value:
        raise TrainingAdmissionError(f"{key} native immutable revision is missing")

    artifact_names: tuple[str, ...]
    artifact = native.get("artifact")
    artifacts = native.get("artifacts")
    if isinstance(artifact, str):
        artifact_names = (artifact,)
    elif isinstance(artifacts, list) and all(
        isinstance(item, str) for item in artifacts
    ):
        artifact_names = tuple(cast(list[str], artifacts))
    else:
        raise TrainingAdmissionError(f"{key} native artifact list is missing")

    artifact_sha = native.get("artifact_sha256")
    if artifact_sha is not None and not isinstance(artifact_sha, str):
        raise TrainingAdmissionError(f"{key} native artifact SHA-256 is invalid")

    chat_format = record.get("tokenizer_chat_format")
    if not isinstance(chat_format, str) or not chat_format:
        raise TrainingAdmissionError(f"{key} tokenizer/chat format is missing")

    return ModelBinding(
        model_key=key,
        role=role,
        native_repository=repository,
        native_revision=revision_value,
        native_artifact_names=artifact_names,
        native_artifact_sha256=artifact_sha,
        tokenizer_chat_format=chat_format,
        model_cast_sha256=model_cast_content_hash(cast_data),
    )


def load_training_config(
    selector: str = "primary",
    *,
    mix: TrainingMix = TrainingMix.JOINT_CORRECTIVE,
    seed: int = 24301,
    profile_version: int = 1,
) -> TrainingConfig:
    """Load the selected model's versioned PEFT profile."""

    binding = resolve_model_binding(selector)
    document = _load_profiles(profile_version)
    if profile_version == 2 and mix is not TrainingMix.JOINT_CORRECTIVE:
        raise TrainingAdmissionError("repair profile admits only joint+corrective")
    if document.get("schema_version") != 1:
        raise TrainingAdmissionError("unsupported training profile schema version")
    profiles = document.get("profiles")
    if not isinstance(profiles, dict):
        raise TrainingAdmissionError("training profiles document is malformed")
    raw_profile = profiles.get(binding.model_key)
    if not isinstance(raw_profile, dict):
        raise TrainingAdmissionError(
            f"no training profile exists for admitted student {binding.model_key}"
        )
    profile = cast(dict[str, Any], raw_profile)
    lora = profile.get("lora")
    if not isinstance(lora, dict):
        raise TrainingAdmissionError("LoRA profile is missing")
    lora_data = cast(dict[str, Any], lora)
    target_modules = lora_data.get("target_modules")
    if not isinstance(target_modules, list) or not all(
        isinstance(item, str) for item in target_modules
    ):
        raise TrainingAdmissionError("LoRA target_modules must be strings")

    return TrainingConfig(
        profile_version=profile_version,
        model_key=binding.model_key,
        backend=str(profile["backend"]),
        method=str(profile["method"]),
        template_strategy=str(profile["template_strategy"]),
        mix=mix,
        seed=seed,
        max_sequence_tokens=int(profile["max_sequence_tokens"]),
        learning_rate=float(profile["learning_rate"]),
        epochs=int(profile["epochs"]),
        micro_batch_size=int(profile["micro_batch_size"]),
        gradient_accumulation_steps=int(profile["gradient_accumulation_steps"]),
        save_steps=int(profile["save_steps"]),
        lora_rank=int(lora_data["rank"]),
        lora_alpha=int(lora_data["alpha"]),
        lora_dropout=float(lora_data["dropout"]),
        lora_target_modules=tuple(cast(list[str], target_modules)),
        parity_max_new_tokens=int(profile["parity_max_new_tokens"]),
    )


def training_config_hash(config: TrainingConfig) -> str:
    """Return canonical identity for one resolved training configuration."""

    return hashlib.sha256(canonical_json(config.to_object()).encode()).hexdigest()


def authorize_heavy_training(
    *,
    gpu_hours: float,
    external_compute_cost_gbp: float,
    paid_model_api_cost_gbp: float = 0.0,
    opt_in: bool,
) -> BudgetAuthorization:
    """Fail closed unless an invocation is explicit and within TTT-012 budget."""

    if not opt_in:
        raise TrainingAdmissionError(
            "heavy training is opt-in; pass an explicit execution admission"
        )
    if gpu_hours <= 0:
        raise TrainingAdmissionError("gpu_hours must be positive for heavy training")
    if external_compute_cost_gbp < 0 or paid_model_api_cost_gbp < 0:
        raise TrainingAdmissionError("cost values must not be negative")

    cast_data = load_model_cast_v1()
    validate_model_cast_v1(cast_data)
    budget = cast(dict[str, Any], cast_data["training_budget"])
    gpu_limit = float(budget["ttt_012_smoke_gpu_hours_max"])
    external_limit = float(budget["external_compute_cost_gbp_max"])
    api_limit = float(budget["paid_model_api_cost_gbp_max"])

    if gpu_hours > gpu_limit:
        raise TrainingAdmissionError(
            f"requested {gpu_hours:g} GPU-hours exceeds TTT-012 limit {gpu_limit:g}"
        )
    if external_compute_cost_gbp > external_limit:
        raise TrainingAdmissionError(
            "requested external compute cost exceeds admitted TTT-012/013 envelope"
        )
    if paid_model_api_cost_gbp > api_limit:
        raise TrainingAdmissionError("paid model/API spend is not admitted")

    return BudgetAuthorization(
        gpu_hours=gpu_hours,
        external_compute_cost_gbp=external_compute_cost_gbp,
        paid_model_api_cost_gbp=paid_model_api_cost_gbp,
    )


def quantization_export_spec(selector: str = "primary") -> JsonObject:
    """Return the opt-in GGUF/Q4 export contract for an admitted runtime target."""

    binding = resolve_model_binding(selector)
    cast_data = load_model_cast_v1()
    profiles = _load_profiles()
    profile_map = cast(dict[str, Any], profiles["profiles"])
    profile = cast(dict[str, Any], profile_map[binding.model_key])
    quant = cast(dict[str, Any], profile["quantization_export"])
    model_map = cast(dict[str, Any], cast_data["models"])
    model_record = cast(dict[str, Any], model_map[binding.model_key])
    inference = cast(dict[str, Any], model_record["inference"])
    probe_defaults = cast(dict[str, Any], cast_data["probe_defaults"])

    result: JsonObject = {
        "enabled_by_default": bool(quant["enabled_by_default"]),
        "format": str(quant["format"]),
        "type": str(quant["type"]),
        "runtime": "llama.cpp",
        "runtime_revision": str(probe_defaults["runtime_revision"]),
        "reference_inference_repository": str(inference["repository"]),
        "reference_inference_artifact_sha256": str(inference["artifact_sha256"]),
        "required_checks": [
            "fixed-format parity before/after export",
            "frozen benchmark quality comparison before runtime admission",
        ],
    }
    return result
