"""Source-frozen, TITAN-only repaired commander execution; never part of CI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

from techrotic_training_triumvirate.evaluation import run_benchmark
from techrotic_training_triumvirate.evaluation.closedloop import run_closed_loop
from techrotic_training_triumvirate.training.admission import (
    load_training_config,
    resolve_model_binding,
)
from techrotic_training_triumvirate.training.campaign import write_json
from techrotic_training_triumvirate.training.commander import (
    CommanderAdapter,
    generate_demonstrations,
    map_commander,
)
from techrotic_training_triumvirate.training.data import load_corpus_examples
from techrotic_training_triumvirate.training.device_admission import GPUSelection
from techrotic_training_triumvirate.training.model import (
    BudgetAuthorization,
    TrainingMix,
)

TITAN = "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8"


def worker(args: argparse.Namespace) -> None:
    from techrotic_training_triumvirate.training.hf_peft import run_hf_peft_training

    def budget_stop() -> None:
        print("HARD BUDGET STOP", flush=True)
        os._exit(124)

    timer = threading.Timer(args.hours * 3600, budget_stop)
    timer.daemon = True
    timer.start()
    args.output.mkdir(parents=True, exist_ok=True)
    config = load_training_config(
        "primary", mix=TrainingMix.JOINT_CORRECTIVE, seed=24302, profile_version=2
    )
    if args.epochs != config.epochs:
        raise ValueError("epochs differ from the admitted versioned profile")
    write_json(args.output / "resolved-config.json", config.to_object())
    binding = resolve_model_binding("primary")
    examples, dataset = load_corpus_examples(args.corpus)
    result_path = args.output / "training-result.json"
    if result_path.exists():
        from techrotic_training_triumvirate.training.campaign_integrity import (
            verify_training_reuse,
        )

        result = verify_training_reuse(
            args.output,
            binding=binding,
            config=config,
            dataset=dataset,
            source_revision=args.git_commit,
        ).result
    else:
        result = run_hf_peft_training(
            tuple(map_commander(e) for e in examples),
            binding=binding,
            config=config,
            dataset=dataset,
            budget=BudgetAuthorization(args.hours, 0, 0),
            output_dir=args.output,
            git_commit=args.git_commit,
        )
    write_json(args.output / "training-result.json", result)
    adapter = CommanderAdapter(
        binding,
        adapter_dir=args.output / "adapter",
        variant="repair-v2",
        revision=result["run_id"],
        policy_id="commander-repair-v2",
        max_new_tokens=192,
        raw_output_path=args.output / "raw-generations.jsonl",
    )
    metadata = {
        "variant": config.mix.value,
        "experiment": "repair-v2",
        "base_checkpoint": binding.to_object(),
        "dataset_hash": dataset.dataset_hash,
        "training_config": config.to_object(),
        "training_run": result["run_id"],
        "gpu_identity": adapter.gpu_identity,
        "runtime": "hf-transformers-peft-native-float32",
        "quantization": "none",
        "decoding": {"do_sample": False, "max_new_tokens": 192},
        "substantive": True,
    }
    write_json(args.output / "candidate-metadata.json", metadata)
    # Separate fresh-seed benchmark used for development before the frozen readout.
    from techrotic_training_triumvirate.evaluation.suite import load_benchmark_v1
    from techrotic_training_triumvirate.schemas import content_hash

    original = load_benchmark_v1()
    cases = tuple(
        replace(c, case_id=f"development-{i}", seed=960000 + i)
        for i, c in enumerate(original.cases)
    )
    development = replace(
        original,
        benchmark_id="ttt-development-v2",
        manifest_hash=content_hash([{"seed": c.seed, "kind": c.kind} for c in cases]),
        generated=tuple(c for c in cases if c.suite == "generated"),
        adversarial=tuple(c for c in cases if c.suite == "adversarial"),
    )
    report = run_benchmark(adapter, code_revision=args.git_commit, manifest=development)
    write_json(args.output / "development.json", report.to_dict())
    mechanical = report.operational["mechanical"]
    dev_closed = report.operational["closed_loop"]
    if (
        args.frozen
        and mechanical["score"] >= 0.95
        and mechanical["rejection_recovery_rate"] >= 0.8
        and dev_closed["objective_completion_rate"] >= 0.8
    ):
        report = run_benchmark(adapter, code_revision=args.git_commit)
        write_json(args.output / "benchmark.json", report.to_dict())
        extended = run_closed_loop(
            adapter, code_revision=args.git_commit, candidate_metadata=metadata
        )
        write_json(args.output / "closed-loop.json", extended.to_dict())
    write_json(
        args.output / "worker-complete.json",
        {"complete": True, "run_id": result["run_id"]},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--gpu-uuid", required=True, choices=[TITAN])
    parser.add_argument("--hours", type=float, default=2)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--corpus-seed", type=int, default=934000)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--frozen", action="store_true")
    args = parser.parse_args()
    if not 0 < args.hours <= 4:
        raise ValueError("one attempt must be bounded to at most four GPU-hours")
    if args.prepare:
        print(
            generate_demonstrations(
                args.corpus, git_commit=args.git_commit, seed=args.corpus_seed
            )
        )
        return 0
    if args.worker:
        worker(args)
        return 0
    # The supervisor is CPU-only; physical selection happens before CUDA import.
    ledger = args.output.parent / "allocation-ledger.json"
    lock = args.output.parent / "allocation.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w") as stream:
        stream.write(str(os.getpid()))
    try:
        state = (
            json.loads(ledger.read_text())
            if ledger.exists()
            else {"charged_gpu_hours": 0, "attempts": []}
        )
        charged = state["charged_gpu_hours"]
        if charged + args.hours > 22:
            raise ValueError("22 GPU-hour allocation exhausted")
        args.output.mkdir(parents=True, exist_ok=True)
        if (args.output / "worker.log").exists():
            raise ValueError("choose a fresh attempt output; failed logs are immutable")
        state["charged_gpu_hours"] += args.hours
        state["attempts"].append(
            {
                "output": str(args.output),
                "status": "reserved",
                "hours": args.hours,
                "source_revision": args.git_commit,
                "gpu_uuid": TITAN,
            }
        )
        write_json(ledger, state)
        started = time.monotonic()
        environment = GPUSelection.from_uuid(TITAN).environment(os.environ)
        environment["PYTHONUNBUFFERED"] = "1"
        with (args.output / "worker.log").open(
            "w", encoding="utf-8", newline="\n"
        ) as log:
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        *sys.argv[1:],
                        "--worker",
                    ],
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=args.hours * 3600 + 15,
                )
                status = result.returncode
            except subprocess.TimeoutExpired:
                status = 124
        actual = min(args.hours, (time.monotonic() - started) / 3600)
        state["charged_gpu_hours"] = charged + actual
        state["attempts"][-1].update(status=status, actual_gpu_hours=actual)
        write_json(ledger, state)
        return status
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
