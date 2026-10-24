"""Operator CLI for deterministic experiment orchestration."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from techrotic_training_triumvirate.schemas import canonical_json

from .adapters import CpuDiagnosticSpec, run_cpu_diagnostic
from .model import (
    EventKind,
    ExperimentContractError,
    ExperimentPlan,
    HumanReview,
    VerifiedEvent,
)
from .rehearsal import run_rehearsal
from .store import ExperimentStore


def add_experiments_parser(subparsers: Any) -> None:
    experiments = subparsers.add_parser(
        "experiments",
        help="validate, inspect and rehearse deterministic experiment plans",
    )
    commands = experiments.add_subparsers(dest="experiment_command", required=True)

    validate = commands.add_parser(
        "validate", help="persist and validate an immutable plan"
    )
    validate.add_argument("plan", type=Path)
    validate.add_argument("--db", type=Path, required=True)

    status = commands.add_parser(
        "status", help="show durable state and budget accounting"
    )
    status.add_argument("experiment_id")
    status.add_argument("--db", type=Path, required=True)

    replay = commands.add_parser(
        "resume", help="replay durable state without relaunching work"
    )
    replay.add_argument("experiment_id")
    replay.add_argument("--db", type=Path, required=True)

    cancel = commands.add_parser(
        "cancel", help="record an explicit cancellation transition"
    )
    cancel.add_argument("experiment_id")
    cancel.add_argument("--db", type=Path, required=True)
    cancel.add_argument("--reason", required=True)
    cancel.add_argument("--timestamp")

    review = commands.add_parser("review", help="import supplied human review")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_import = review_commands.add_parser("import")
    review_import.add_argument("experiment_id")
    review_import.add_argument("ratings", type=Path)
    review_import.add_argument("--db", type=Path, required=True)

    verify = commands.add_parser(
        "verify", help="replay and verify the persisted event chain"
    )
    verify.add_argument("experiment_id")
    verify.add_argument("--db", type=Path, required=True)

    rehearse = commands.add_parser(
        "rehearse", help="run a complete deterministic simulation with zero LLM calls"
    )
    rehearse.add_argument("--db", type=Path, required=True)
    rehearse.add_argument("--output", type=Path, required=True)
    rehearse.add_argument("--review", type=Path, required=True)

    diagnostic = commands.add_parser(
        "cpu-diagnostic",
        help="run one fixed CPU conversion/inference command as non-admission evidence",
    )
    diagnostic.add_argument("--cwd", type=Path, required=True)
    diagnostic.add_argument("--output", type=Path, required=True)
    diagnostic.add_argument("--timeout", type=float, default=600.0)
    diagnostic.add_argument("--artifact", type=Path)
    diagnostic.add_argument("tool", type=Path)
    diagnostic.add_argument("tool_args", nargs=argparse.REMAINDER)


def _load_review(path: Path) -> HumanReview:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentContractError(f"cannot read supplied review: {exc}") from exc
    return HumanReview.from_object(value)


def run_experiments(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        if args.experiment_command == "validate":
            plan = ExperimentPlan.from_json(args.plan)
            with ExperimentStore(args.db) as store:
                experiment_id = store.create_plan(plan)
                state = store.append_event(
                    experiment_id,
                    VerifiedEvent(
                        event_id="plan-validated",
                        kind=EventKind.PLAN_VALIDATED,
                        timestamp=plan.created_at,
                        payload={"experiment_id": experiment_id},
                    ),
                )
            print(
                canonical_json(
                    {
                        "experiment_id": experiment_id,
                        "state": state.value,
                        "validated": True,
                    }
                )
            )
            return 0

        if args.experiment_command == "status":
            with ExperimentStore(args.db) as store:
                state, hashes = store.replay(args.experiment_id)
                result = {
                    "experiment_id": args.experiment_id,
                    "state": state.value,
                    "event_count": len(hashes),
                    "budget": store.budget_snapshot(args.experiment_id),
                    "artifacts": list(store.artifact_inventory(args.experiment_id)),
                }
            print(canonical_json(result))
            return 0

        if args.experiment_command == "resume":
            with ExperimentStore(args.db) as store:
                state, hashes = store.replay(args.experiment_id)
            print(
                canonical_json(
                    {
                        "experiment_id": args.experiment_id,
                        "state": state.value,
                        "event_chain": list(hashes),
                        "relaunched": False,
                    }
                )
            )
            return 0

        if args.experiment_command == "cancel":
            timestamp = args.timestamp or datetime.now(UTC).isoformat()
            with ExperimentStore(args.db) as store:
                state = store.append_event(
                    args.experiment_id,
                    VerifiedEvent(
                        event_id=f"cancel-{timestamp}",
                        kind=EventKind.CANCEL_REQUESTED,
                        timestamp=timestamp,
                        payload={"reason": args.reason},
                    ),
                )
            print(canonical_json({"state": state.value, "cancel_recorded": True}))
            return 0

        if args.experiment_command == "review" and args.review_command == "import":
            review = _load_review(args.ratings)
            with ExperimentStore(args.db) as store:
                plan = store.plan(args.experiment_id)
                if plan.evidence_class.value == "admission" and review.test_fixture:
                    raise ExperimentContractError(
                        "test review cannot advance an admission experiment"
                    )
                state = store.append_event(
                    args.experiment_id,
                    VerifiedEvent(
                        event_id=f"review-{review.packet_id}-{review.reviewer_id}",
                        kind=EventKind.HUMAN_REVIEW_IMPORTED,
                        timestamp=review.submitted_at,
                        payload=review.to_object(),
                    ),
                )
            print(canonical_json({"state": state.value, "review_imported": True}))
            return 0

        if args.experiment_command == "verify":
            with ExperimentStore(args.db) as store:
                plan = store.plan(args.experiment_id)
                state, hashes = store.replay(args.experiment_id)
            print(
                canonical_json(
                    {
                        "controller_verified": True,
                        "experiment_id": args.experiment_id,
                        "state": state.value,
                        "events": len(hashes),
                        "evidence_class": plan.evidence_class.value,
                    }
                )
            )
            return 0

        if args.experiment_command == "rehearse":
            result = run_rehearsal(
                args.db, args.output, review=_load_review(args.review)
            )
            print(canonical_json(result))
            return 0

        if args.experiment_command == "cpu-diagnostic":
            result = run_cpu_diagnostic(
                CpuDiagnosticSpec(
                    tool=args.tool,
                    args=tuple(args.tool_args),
                    cwd=args.cwd,
                    output_dir=args.output,
                    timeout_seconds=args.timeout,
                    artifact=args.artifact,
                )
            )
            print(canonical_json(result))
            return 0
    except (OSError, ValueError) as exc:
        parser.exit(1, f"experiment command failed: {exc}\n")

    parser.error("unknown experiment command")
    return 2
