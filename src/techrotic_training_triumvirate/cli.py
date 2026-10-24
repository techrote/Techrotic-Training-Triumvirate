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

    parser.print_help()
    return 0
