"""Explicit local pilot corpus generation and bounded four-way native training."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from techrotic_training_triumvirate.training.campaign import (
    prepare_pilot_corpus,
    run_pilot_campaign,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-corpus", action="store_true")
    parser.add_argument("--episodes-per-tier", type=int, default=12)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--corpus-seed", type=int, default=750000)
    parser.add_argument("--seed", type=int, default=24301)
    parser.add_argument("--execution-host", default=platform.node())
    parser.add_argument("--allocation-id", required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--gpu-hours", type=float, default=4.0)
    parser.add_argument("--gpu-index", type=int, default=0)
    parser.add_argument("--allow-heavy", action="store_true")
    args = parser.parse_args()
    if args.prepare_corpus:
        identity = prepare_pilot_corpus(
            args.corpus,
            seed=args.corpus_seed,
            episodes_per_tier=args.episodes_per_tier,
            turns=args.turns,
            git_commit=args.git_commit,
        )
        write_json(args.output / "corpus-identity.json", identity)
    dependencies = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "dependencies.txt").write_text(dependencies, encoding="utf-8")
    result = run_pilot_campaign(
        args.corpus,
        args.output,
        execution_host=args.execution_host,
        allocation_id=args.allocation_id,
        git_commit=args.git_commit,
        allow_heavy=args.allow_heavy,
        gpu_hours=args.gpu_hours,
        seed=args.seed,
        gpu_index=args.gpu_index,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
