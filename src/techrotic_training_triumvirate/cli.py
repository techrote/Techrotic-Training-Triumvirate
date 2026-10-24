"""Command-line entry point for the lightweight TTT core package."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TTT developer CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

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
