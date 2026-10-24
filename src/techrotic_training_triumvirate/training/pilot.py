"""TTT-013 pilot-corpus admission, ablation planning, and smoke orchestration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.evaluation import frozen_evaluation_guard
from techrotic_training_triumvirate.model_admission import (
    load_model_cast_v1,
    validate_model_cast_v1,
)
from techrotic_training_triumvirate.schemas import JsonObject, JsonValue, canonical_json

from .admission import load_training_config, resolve_model_binding
from .data import (
    dataset_identity_from_examples,
    load_corpus_examples,
    map_dataset,
    smoke_source_examples,
)
from .export import export_tiny
from .model import TrainingMix
from .tiny import train_tiny

PILOT_MIXES: tuple[TrainingMix, ...] = (
    TrainingMix.OPERATIONAL,
    TrainingMix.PERSONA,
    TrainingMix.JOINT,
    TrainingMix.JOINT_CORRECTIVE,
)


class PilotPreparationError(ValueError):
    """Raised when a TTT-013 pilot preparation violates an admission contract."""


def pilot_budget_limits() -> JsonObject:
    """Return the immutable TTT-013 ceiling admitted by TTT-011."""

    cast_data = load_model_cast_v1()
    validate_model_cast_v1(cast_data)
    budget = cast(dict[str, Any], cast_data["training_budget"])
    return {
        "gpu_hours_max": float(budget["ttt_013_initial_pilot_gpu_hours_max"]),
        "external_compute_cost_gbp_max": float(
            budget["external_compute_cost_gbp_max"]
        ),
        "paid_model_api_cost_gbp_max": float(budget["paid_model_api_cost_gbp_max"]),
        "rule": str(budget["rule"]),
    }


def authorize_pilot_budget(
    *,
    gpu_hours: float,
    external_compute_cost_gbp: float,
    paid_model_api_cost_gbp: float = 0.0,
    opt_in: bool,
) -> JsonObject:
    """Validate one explicit TTT-013 execution admission without spending it."""

    if not opt_in:
        raise PilotPreparationError(
            "TTT-013 heavy execution is opt-in; explicit execution admission required"
        )
    if gpu_hours <= 0:
        raise PilotPreparationError("pilot gpu_hours must be positive")
    if external_compute_cost_gbp < 0 or paid_model_api_cost_gbp < 0:
        raise PilotPreparationError("pilot cost values must not be negative")

    limits = pilot_budget_limits()
    gpu_max = float(limits["gpu_hours_max"])
    cost_max = float(limits["external_compute_cost_gbp_max"])
    api_max = float(limits["paid_model_api_cost_gbp_max"])
    if gpu_hours > gpu_max:
        raise PilotPreparationError(
            f"requested {gpu_hours:g} GPU-hours exceeds TTT-013 limit {gpu_max:g}"
        )
    if external_compute_cost_gbp > cost_max:
        raise PilotPreparationError(
            "requested external compute cost exceeds the admitted TTT-013 envelope"
        )
    if paid_model_api_cost_gbp > api_max:
        raise PilotPreparationError("paid model/API spend is not admitted")

    return {
        "gpu_hours": gpu_hours,
        "external_compute_cost_gbp": external_compute_cost_gbp,
        "paid_model_api_cost_gbp": paid_model_api_cost_gbp,
    }


def validate_pilot_manifest(manifest: JsonObject) -> None:
    """Require representative T1/T2/T3 data and zero frozen benchmark examples."""

    tiers = manifest.get("tier_composition")
    if not isinstance(tiers, dict):
        raise PilotPreparationError("pilot corpus has no tier_composition")
    for tier in ("T1", "T2", "T3"):
        count = tiers.get(tier, 0)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise PilotPreparationError(
                f"pilot corpus requires at least one admitted {tier} example"
            )

    split_distribution = manifest.get("split_distribution")
    if not isinstance(split_distribution, dict):
        raise PilotPreparationError("pilot corpus has no split_distribution")
    frozen_count = split_distribution.get("frozen_eval", 0)
    if not isinstance(frozen_count, int) or isinstance(frozen_count, bool):
        raise PilotPreparationError("frozen_eval split count must be an integer")
    if frozen_count:
        raise PilotPreparationError(
            "pilot corpus contains frozen evaluation examples; benchmark worlds "
            "must be excluded rather than copied into TTT-013 training"
        )

    shards = manifest.get("shards")
    if not isinstance(shards, list):
        raise PilotPreparationError("pilot corpus has no shard manifest")
    for raw_shard in shards:
        if not isinstance(raw_shard, dict):
            raise PilotPreparationError("pilot shard manifest entry must be an object")
        if raw_shard.get("split") != "frozen_eval":
            continue
        line_count = raw_shard.get("line_count", 0)
        if not isinstance(line_count, int) or isinstance(line_count, bool):
            raise PilotPreparationError("pilot shard line_count must be an integer")
        if line_count:
            raise PilotPreparationError(
                "pilot corpus contains a non-empty frozen_eval shard"
            )

    config = manifest.get("config")
    if not isinstance(config, dict):
        raise PilotPreparationError("pilot corpus has no corpus configuration")
    recorded_guard = config.get("frozen_evaluation_guard")
    if not isinstance(recorded_guard, dict):
        raise PilotPreparationError("pilot corpus does not bind the TTT-009 guard")
    guard = frozen_evaluation_guard()
    expected = {
        "benchmark_id": guard.benchmark_id,
        "benchmark_version": guard.benchmark_version,
        "benchmark_hash": guard.benchmark_hash,
    }
    for key, value in expected.items():
        if recorded_guard.get(key) != value:
            raise PilotPreparationError(
                f"pilot corpus frozen-evaluation guard mismatch for {key}"
            )


def _load_pilot_corpus(
    corpus_dir: str | Path,
) -> tuple[JsonObject, JsonObject]:
    root = Path(corpus_dir)
    raw_manifest = root.joinpath("manifest.json").read_text(encoding="utf-8")
    parsed: object = json.loads(raw_manifest)
    if not isinstance(parsed, dict):
        raise PilotPreparationError("pilot corpus manifest must be an object")
    manifest = cast(JsonObject, parsed)
    validate_pilot_manifest(manifest)
    _sources, dataset = load_corpus_examples(root)
    return manifest, dataset.to_object()


def pilot_variant_matrix(
    *,
    model: str = "primary",
    seed: int = 24301,
    gpu_hours: float = 24.0,
    external_compute_cost_gbp: float = 75.0,
) -> tuple[JsonObject, ...]:
    """Build four directly comparable variant configurations within TTT-013."""

    authorize_pilot_budget(
        gpu_hours=gpu_hours,
        external_compute_cost_gbp=external_compute_cost_gbp,
        opt_in=True,
    )
    binding = resolve_model_binding(model)
    per_variant_gpu = gpu_hours / len(PILOT_MIXES)
    per_variant_cost = external_compute_cost_gbp / len(PILOT_MIXES)
    variants: list[JsonObject] = []
    for mix in PILOT_MIXES:
        config = load_training_config(model, mix=mix, seed=seed)
        variants.append(
            {
                "variant_id": mix.value,
                "mix": mix.value,
                "model_binding": binding.to_object(),
                "training_config": config.to_object(),
                "budget_cap": {
                    "gpu_hours": per_variant_gpu,
                    "external_compute_cost_gbp": per_variant_cost,
                    "paid_model_api_cost_gbp": 0.0,
                },
            }
        )
    return tuple(variants)


def build_pilot_plan(
    corpus_dir: str | Path,
    *,
    model: str = "primary",
    seed: int = 24301,
    gpu_hours: float = 24.0,
    external_compute_cost_gbp: float = 75.0,
    execution_host: str | None = None,
    allocation_id: str | None = None,
) -> JsonObject:
    """Freeze the content-addressed TTT-013 experiment plan without executing it."""

    manifest, dataset = _load_pilot_corpus(corpus_dir)
    variants = pilot_variant_matrix(
        model=model,
        seed=seed,
        gpu_hours=gpu_hours,
        external_compute_cost_gbp=external_compute_cost_gbp,
    )
    guard = frozen_evaluation_guard()
    has_allocation = bool(
        execution_host
        and execution_host.strip()
        and allocation_id
        and allocation_id.strip()
    )
    blocker = (
        None
        if has_allocation
        else (
            "TTT-011 records a budget ceiling but the repository records no admitted "
            "TTT-013 GPU execution host/allocation. Substantive fine-tunes must not "
            "start until that execution admission is supplied."
        )
    )
    variant_values: list[JsonValue] = [item for item in variants]
    omitted_values: list[JsonValue] = []
    if blocker is not None:
        omitted_values = [
            {
                "variant_id": mix.value,
                "reason": blocker,
            }
            for mix in PILOT_MIXES
        ]

    plan: JsonObject = {
        "schema": "ttt.pilot_ablation_plan",
        "schema_version": 1,
        "dataset_identity": dataset,
        "corpus_statistics": {
            "counts": manifest.get("counts", {}),
            "tier_composition": manifest.get("tier_composition", {}),
            "split_distribution": manifest.get("split_distribution", {}),
            "teacher_contribution": manifest.get("teacher_contribution", {}),
            "rejection_reasons": manifest.get("rejection_reasons", {}),
            "error_distribution": manifest.get("error_distribution", {}),
        },
        "benchmark_clean": True,
        "frozen_evaluation_guard": {
            "benchmark_id": guard.benchmark_id,
            "benchmark_version": guard.benchmark_version,
            "benchmark_hash": guard.benchmark_hash,
        },
        "comparison_contract": {
            "same_base_checkpoint": True,
            "same_seed": seed,
            "same_training_profile_except_mix": True,
            "variants": variant_values,
        },
        "budget": {
            "requested": {
                "gpu_hours": gpu_hours,
                "external_compute_cost_gbp": external_compute_cost_gbp,
                "paid_model_api_cost_gbp": 0.0,
            },
            "limits": pilot_budget_limits(),
        },
        "evaluation": {
            "benchmark": "TTT-009 / ttt-core-frozen v1",
            "required_for_every_real_candidate": True,
            "mechanical_and_persona_reported_separately": True,
            "training_loss_is_not_runtime_admission": True,
        },
        "execution": {
            "status": (
                "prepared_execution_admission_present"
                if has_allocation
                else "prepared_blocked_no_execution_allocation"
            ),
            "execution_host": execution_host,
            "allocation_id": allocation_id,
            "substantive_training_executed": False,
            "blocker": blocker,
        },
        "omitted_substantive_runs": omitted_values,
    }
    identity_payload = dict(plan)
    plan["plan_sha256"] = hashlib.sha256(
        canonical_json(cast(JsonObject, identity_payload)).encode("utf-8")
    ).hexdigest()
    return plan


def _variant_slug(mix: TrainingMix) -> str:
    return mix.value.replace("+", "-")


def run_pilot_smoke(
    output_dir: str | Path,
    *,
    model: str = "primary",
    seed: int = 24301,
    git_commit: str = "working-tree",
) -> JsonObject:
    """Run all four variants on the deterministic tiny backend only."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    sources = smoke_source_examples()
    dataset = dataset_identity_from_examples(sources)
    binding = resolve_model_binding(model)
    variants: list[JsonValue] = []

    for mix in PILOT_MIXES:
        mapped = map_dataset(sources, mix=mix)
        config = load_training_config(model, mix=mix, seed=seed)
        variant_dir = root / _variant_slug(mix)
        trained = train_tiny(
            mapped,
            binding=binding,
            config=config,
            dataset=dataset,
            checkpoint_path=variant_dir / "checkpoint.json",
        )
        exported = export_tiny(
            trained,
            mapped,
            binding=binding,
            config=config,
            dataset=dataset,
            output_dir=variant_dir / "export",
            git_commit=git_commit,
        )
        variants.append(
            {
                "variant_id": mix.value,
                "mapped_example_count": len(mapped),
                "completed_steps": trained.completed_steps,
                "model_hash": trained.model_hash,
                "parity_passed": cast(dict[str, Any], exported["parity"])["passed"],
            }
        )

    result: JsonObject = {
        "schema": "ttt.pilot_ablation_smoke",
        "schema_version": 1,
        "model_binding": binding.to_object(),
        "dataset_identity": dataset.to_object(),
        "seed": seed,
        "variants": variants,
        "quality_evidence": False,
        "substantive_campaign_executed": False,
        "evaluation_status": "not-a-real-candidate-control-plane-smoke",
        "blocker": (
            "No admitted TTT-013 GPU execution host/allocation is recorded. "
            "These tiny runs prove orchestration, export, parity, and mix separation "
            "only; they are not LFM/Qwen quality evidence."
        ),
    }
    result["smoke_sha256"] = hashlib.sha256(
        canonical_json(result).encode("utf-8")
    ).hexdigest()
    root.joinpath("smoke-comparison.json").write_text(
        f"{canonical_json(result)}\n",
        encoding="utf-8",
        newline="\n",
    )
    return result
