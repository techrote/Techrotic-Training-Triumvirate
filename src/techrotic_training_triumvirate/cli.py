"""Command-line entry point for the lightweight TTT core package."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .determinism import DEFAULT_TEST_SEED, stable_u64_sequence


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser."""
    parser = argparse.ArgumentParser(
        prog="ttt",
        description="Techrotic Training Triumvirate developer CLI.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")
    seed_demo = subparsers.add_parser(
        "seed-demo",
        help="emit a deterministic sequence for a supplied seed",
    )
    seed_demo.add_argument("--seed", type=int, default=DEFAULT_TEST_SEED)
    seed_demo.add_argument("--count", type=int, default=5)

    schema = subparsers.add_parser(
        "schema-bundle",
        help="emit the canonical JSON Schema bundle",
    )
    schema.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print instead of canonical compact JSON",
    )

    command_schema_parser = subparsers.add_parser(
        "command-schema",
        help="emit the TTT command protocol JSON Schema",
    )
    command_schema_parser.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print instead of compact JSON",
    )

    world_demo = subparsers.add_parser(
        "world-demo",
        help="run the deterministic abstract World Authority reference episode",
    )
    world_demo.add_argument("--seed", type=int, default=DEFAULT_TEST_SEED)
    world_demo.add_argument("--turns", type=int, default=24)
    world_demo.add_argument("--mid-state", action="store_true")

    admission_verify = subparsers.add_parser(
        "admission-verify",
        help="verify the final admission package and evidence hashes",
    )
    admission_verify.add_argument("--package", required=True)
    admission_verify.add_argument("--root", required=True, help="trusted evidence root")

    evaluate = subparsers.add_parser(
        "evaluate", help="run the model-free frozen evaluation baseline"
    )
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--code-revision", required=True)

    closed_loop = subparsers.add_parser(
        "closed-loop", help="run the scripted frozen 24-turn baseline and rating packet"
    )
    closed_loop.add_argument("--output", type=Path, required=True)
    closed_loop.add_argument("--code-revision", required=True)

    replay = subparsers.add_parser(
        "closed-loop-verify",
        help="replay a stored closed-loop report without the model",
    )
    replay.add_argument("--report", type=Path, required=True)

    runtime_demo = subparsers.add_parser(
        "runtime-demo",
        help="run a JSON runtime session with grounded player intercepts",
    )
    runtime_demo.add_argument("--seed", type=int, default=DEFAULT_TEST_SEED)
    runtime_demo.add_argument("--turns", type=int, default=4)
    runtime_demo.add_argument("--output", type=Path)

    from .experiments.cli import add_experiments_parser

    add_experiments_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TTT developer CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "experiments":
        from .experiments.cli import run_experiments

        return run_experiments(args, parser)

    if args.command == "runtime-demo":
        from .runtime import run_runtime_demo
        from .schemas import canonical_json

        try:
            runtime_report = run_runtime_demo(seed=args.seed, turns=args.turns)
        except ValueError as exc:
            parser.exit(1, f"runtime demo failed: {exc}\n")
        encoded = canonical_json(runtime_report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded + "\n", encoding="utf-8", newline="\n")
        print(encoded)
        return 0

    if args.command == "admission-verify":
        from .admission import AdmissionPackageError, verify_package

        try:
            admission_result = verify_package(args.package, evidence_root=args.root)
        except AdmissionPackageError as exc:
            parser.exit(1, f"admission verification failed: {exc}\n")
        print(json.dumps(admission_result, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "evaluate":
        from .evaluation import ScriptedCommanderBaseline, run_benchmark

        benchmark = run_benchmark(
            ScriptedCommanderBaseline(), code_revision=args.code_revision
        )
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "frozen-evaluation.json").write_text(
            benchmark.to_json() + "\n", encoding="utf-8", newline="\n"
        )
        (args.output / "frozen-evaluation.md").write_text(
            benchmark.to_markdown(), encoding="utf-8", newline="\n"
        )
        print(json.dumps({"report_hash": benchmark.report_hash()}, sort_keys=True))
        return 0

    if args.command == "closed-loop":
        from .evaluation.closedloop import (
            ClosedLoopBaseline,
            run_closed_loop,
            write_closed_loop_comparison,
        )

        report = run_closed_loop(ClosedLoopBaseline(), code_revision=args.code_revision)
        write_closed_loop_comparison([report], args.output)
        print(json.dumps({"semantic_hash": report.semantic_hash()}, sort_keys=True))
        return 0

    if args.command == "closed-loop-verify":
        from .evaluation.closedloop import verify_closed_loop_report

        try:
            payload = json.loads(args.report.read_text(encoding="utf-8"))
            verified = verify_closed_loop_report(payload)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.exit(1, f"closed-loop verification failed: {exc}\n")
        print(json.dumps({"verified": True, "semantic_hash": verified.semantic_hash()}))
        return 0

    if args.command == "seed-demo":
        values = stable_u64_sequence(args.seed, args.count)
        print(
            json.dumps(
                {
                    "count": args.count,
                    "seed": args.seed,
                    "values": values,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    if args.command == "schema-bundle":
        from .schemas import schema_bundle

        bundle = schema_bundle()
        if args.pretty:
            print(json.dumps(bundle, indent=2, sort_keys=True))
        else:
            print(
                json.dumps(
                    bundle,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        return 0

    if args.command == "command-schema":
        from .commands import command_schema

        schema = command_schema()
        if args.pretty:
            print(json.dumps(schema, indent=2, sort_keys=True))
        else:
            print(json.dumps(schema, sort_keys=True, separators=(",", ":")))
        return 0

    if args.command == "world-demo":
        from .world import run_scripted_episode

        result = run_scripted_episode(
            seed=args.seed,
            turns=args.turns,
            mid_state=args.mid_state,
        )
        failure_codes = [
            event.data.get("code")
            for event in result.events
            if event.kind == "execution-failed"
        ]
        print(
            json.dumps(
                {
                    "seed": args.seed,
                    "turns": args.turns,
                    "mid_state": args.mid_state,
                    "accepted": sum(item.accepted for item in result.results),
                    "rejected": sum(not item.accepted for item in result.results),
                    "events": len(result.events),
                    "failure_codes": failure_codes,
                    "final_state_hash": result.final_state_hash,
                    "event_hash": result.event_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0

    parser.print_help()
    return 0
