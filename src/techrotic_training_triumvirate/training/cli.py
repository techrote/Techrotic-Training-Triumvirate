"""TTT-012 training/export command line."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from techrotic_training_triumvirate.schemas import canonical_json

from .admission import (
    authorize_heavy_training,
    load_training_config,
    quantization_export_spec,
    resolve_model_binding,
)
from .data import (
    dataset_identity_from_examples,
    load_corpus_examples,
    map_dataset,
    smoke_source_examples,
)
from .export import export_tiny
from .hf_peft import run_hf_peft_training
from .model import TrainingMix
from .tiny import train_tiny


def _mix(value: str) -> TrainingMix:
    try:
        return TrainingMix(value)
    except ValueError as exc:
        choices = ", ".join(item.value for item in TrainingMix)
        raise argparse.ArgumentTypeError(
            f"unknown mix {value!r}; choose one of: {choices}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ttt-train",
        description="Reproducible TTT fine-tuning/export harness.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    profiles = subparsers.add_parser(
        "profile",
        help="show the resolved admitted model/training/export configuration",
    )
    profiles.add_argument("--model", default="primary")
    profiles.add_argument(
        "--mix",
        type=_mix,
        default=TrainingMix.JOINT_CORRECTIVE,
    )
    profiles.add_argument("--seed", type=int, default=24301)

    smoke = subparsers.add_parser(
        "smoke",
        help="run deterministic CPU-small smoke training/export/parity",
    )
    smoke.add_argument("--model", default="primary")
    smoke.add_argument(
        "--mix",
        type=_mix,
        default=TrainingMix.JOINT_CORRECTIVE,
    )
    smoke.add_argument("--seed", type=int, default=24301)
    smoke.add_argument("--output", type=Path, required=True)
    smoke.add_argument("--git-commit", default="working-tree")

    plan = subparsers.add_parser(
        "plan-heavy",
        help=(
            "validate an explicit heavyweight execution request against "
            "TTT-012 budget"
        ),
    )
    plan.add_argument("--model", default="primary")
    plan.add_argument(
        "--mix",
        type=_mix,
        default=TrainingMix.JOINT_CORRECTIVE,
    )
    plan.add_argument("--seed", type=int, default=24301)
    plan.add_argument("--gpu-hours", type=float, required=True)
    plan.add_argument("--external-cost-gbp", type=float, required=True)
    plan.add_argument("--allow-heavy", action="store_true")

    train_hf = subparsers.add_parser(
        "train-hf",
        help="run opt-in native-checkpoint PEFT LoRA training and export",
    )
    train_hf.add_argument("--corpus", type=Path, required=True)
    train_hf.add_argument("--output", type=Path, required=True)
    train_hf.add_argument("--model", default="primary")
    train_hf.add_argument(
        "--mix",
        type=_mix,
        default=TrainingMix.JOINT_CORRECTIVE,
    )
    train_hf.add_argument("--seed", type=int, default=24301)
    train_hf.add_argument("--gpu-hours", type=float, required=True)
    train_hf.add_argument("--external-cost-gbp", type=float, required=True)
    train_hf.add_argument("--allow-heavy", action="store_true")
    train_hf.add_argument("--git-commit", required=True)
    train_hf.add_argument("--resume-from-checkpoint")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "profile":
        binding = resolve_model_binding(args.model)
        config = load_training_config(
            args.model,
            mix=args.mix,
            seed=args.seed,
        )
        payload = {
            "model_binding": binding.to_object(),
            "training_config": config.to_object(),
            "quantization_export": quantization_export_spec(args.model),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "smoke":
        sources = smoke_source_examples()
        dataset = dataset_identity_from_examples(sources)
        mapped = map_dataset(sources, mix=args.mix)
        binding = resolve_model_binding(args.model)
        config = load_training_config(
            args.model,
            mix=args.mix,
            seed=args.seed,
        )
        checkpoint = args.output / "checkpoint.json"
        trained = train_tiny(
            mapped,
            binding=binding,
            config=config,
            dataset=dataset,
            checkpoint_path=checkpoint,
        )
        exported = export_tiny(
            trained,
            mapped,
            binding=binding,
            config=config,
            dataset=dataset,
            output_dir=args.output / "export",
            git_commit=args.git_commit,
        )
        print(canonical_json(exported))
        return 0

    if args.command == "plan-heavy":
        binding = resolve_model_binding(args.model)
        config = load_training_config(
            args.model,
            mix=args.mix,
            seed=args.seed,
        )
        budget = authorize_heavy_training(
            gpu_hours=args.gpu_hours,
            external_compute_cost_gbp=args.external_cost_gbp,
            opt_in=args.allow_heavy,
        )
        payload = {
            "model_binding": binding.to_object(),
            "training_config": config.to_object(),
            "budget": budget.to_object(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "train-hf":
        sources, dataset = load_corpus_examples(args.corpus)
        mapped = map_dataset(sources, mix=args.mix)
        binding = resolve_model_binding(args.model)
        config = load_training_config(
            args.model,
            mix=args.mix,
            seed=args.seed,
        )
        budget = authorize_heavy_training(
            gpu_hours=args.gpu_hours,
            external_compute_cost_gbp=args.external_cost_gbp,
            opt_in=args.allow_heavy,
        )
        result = run_hf_peft_training(
            mapped,
            binding=binding,
            config=config,
            dataset=dataset,
            budget=budget,
            output_dir=args.output,
            git_commit=args.git_commit,
            resume_from_checkpoint=args.resume_from_checkpoint,
        )
        print(canonical_json(result))
        return 0

    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
