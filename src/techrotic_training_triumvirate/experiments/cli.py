"""Operator CLI for deterministic TTT experiment state."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from techrotic_training_triumvirate.schemas import JsonObject, canonical_json

from .model import ExperimentPlan, OrchestrationError
from .rehearsal import run_rehearsal
from .store import ExperimentStore


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("build/ttt-experiments.sqlite3"),
        help="SQLite orchestration database",
    )
    subparsers = parser.add_subparsers(dest="experiment_command", required=True)

    validate = subparsers.add_parser("validate", help="validate an immutable plan")
    validate.add_argument("plan", type=Path)

    run = subparsers.add_parser(
        "run",
        help="register a validated plan and enter deterministic preflight",
    )
    run.add_argument("plan", type=Path)
    run.add_argument(
        "--detach",
        action="store_true",
        help="record operator intent; worker hosts detach only when later launched",
    )

    status = subparsers.add_parser("status", help="show durable experiment status")
    status.add_argument("experiment_id")
    status.add_argument("--json", action="store_true")

    resume = subparsers.add_parser(
        "resume",
        help="replay durable state without blindly relaunching a worker",
    )
    resume.add_argument("experiment_id")

    cancel = subparsers.add_parser("cancel", help="request deterministic cancellation")
    cancel.add_argument("experiment_id")
    cancel.add_argument("--reason", required=True)

    verify = subparsers.add_parser(
        "verify",
        help="replay and verify the append-only event journal",
    )
    verify.add_argument("experiment_id")

    review = subparsers.add_parser("review", help="import an explicit review record")
    review_subparsers = review.add_subparsers(dest="review_command", required=True)
    review_import = review_subparsers.add_parser("import")
    review_import.add_argument("experiment_id")
    review_import.add_argument("ratings", type=Path)
    review_import.add_argument("--candidate-id", required=True)
    review_import.add_argument("--packet-id", required=True)
    review_import.add_argument(
        "--class", dest="review_class", choices=("human", "test")
    )

    rehearse = subparsers.add_parser(
        "rehearse",
        help="run the complete deterministic test-only pipeline",
    )
    rehearse.add_argument("--output", type=Path, required=True)
    rehearse.add_argument("--review", type=Path, required=True)


def _read_object(path: Path, *, field: str) -> JsonObject:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrchestrationError(f"{field} is unreadable") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise OrchestrationError(f"{field} must be a JSON object")
    return dict(value)


def _read_plan(path: Path) -> ExperimentPlan:
    return ExperimentPlan.from_object(_read_object(path, field="experiment plan"))


def _read_ratings(path: Path) -> dict[str, int]:
    value = _read_object(path, field="review ratings")
    result: dict[str, int] = {}
    for key, item in value.items():
        if isinstance(item, bool) or not isinstance(item, int):
            raise OrchestrationError("review ratings must be integers")
        result[key] = item
    return result


def _emit(value: JsonObject) -> None:
    print(canonical_json(value))


def handle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        command = str(args.experiment_command)
        if command == "validate":
            plan = _read_plan(args.plan)
            _emit(
                {
                    "valid": True,
                    "experiment_id": plan.experiment_id,
                    "simulation": plan.simulation,
                }
            )
            return 0

        if command == "rehearse":
            ratings = _read_ratings(args.review)
            report = run_rehearsal(args.db, args.output, review_ratings=ratings)
            _emit(report)
            return 0

        if command == "run":
            plan = _read_plan(args.plan)
            if plan.simulation:
                raise OrchestrationError(
                    "simulation plans use 'experiments rehearse' with supplied review"
                )
            with ExperimentStore(args.db) as store:
                experiment_id = store.create_experiment(
                    plan, timestamp_ns=time.time_ns()
                )
                store.append_event(
                    experiment_id,
                    "PLAN_VALIDATED",
                    {
                        "operator_detach_requested": bool(args.detach),
                        "llm_calls": 0,
                    },
                    timestamp_ns=time.time_ns(),
                    idempotency_key="operator-run",
                )
                status = store.status(experiment_id)
                status["next_action"] = "run_preflight"
                _emit(status)
            return 0

        experiment_id = str(args.experiment_id)
        with ExperimentStore(args.db) as store:
            if command == "status":
                status = store.status(experiment_id)
                if args.json:
                    _emit(status)
                else:
                    print(
                        f"{status['experiment_id']} {status['state']} "
                        f"events={status['event_count']}"
                    )
                return 0
            if command == "resume":
                state = store.replay(experiment_id)
                status = store.status(experiment_id)
                status["replayed_state"] = state.value
                status["relaunch_performed"] = False
                _emit(status)
                return 0
            if command == "cancel":
                event = store.append_event(
                    experiment_id,
                    "CANCEL_REQUESTED",
                    {"reason": str(args.reason)},
                    timestamp_ns=time.time_ns(),
                    idempotency_key=f"cancel:{args.reason}",
                )
                _emit(
                    {
                        "experiment_id": experiment_id,
                        "state": event.state_after.value,
                        "event_id": event.event_id,
                    }
                )
                return 0
            if command == "verify":
                state = store.replay(experiment_id)
                plan = store.load_plan(experiment_id)
                _emit(
                    {
                        "verified": True,
                        "experiment_id": experiment_id,
                        "state": state.value,
                        "simulation": plan.simulation,
                        "qualifies_candidate": False if plan.simulation else None,
                    }
                )
                return 0
            if command == "review" and args.review_command == "import":
                plan = store.load_plan(experiment_id)
                review_class = (
                    str(args.review_class)
                    if args.review_class is not None
                    else ("test" if plan.simulation else "human")
                )
                ratings = _read_ratings(args.ratings)
                imported_at = time.time_ns()
                review_id = store.record_review(
                    experiment_id,
                    candidate_id=str(args.candidate_id),
                    packet_id=str(args.packet_id),
                    ratings=ratings,
                    review_class=review_class,
                    imported_at_ns=imported_at,
                )
                event = store.append_event(
                    experiment_id,
                    "HUMAN_REVIEW_IMPORTED",
                    {
                        "review_id": review_id,
                        "review_class": review_class,
                        "candidate_id": str(args.candidate_id),
                    },
                    timestamp_ns=imported_at,
                    idempotency_key=review_id,
                )
                _emit(
                    {
                        "review_id": review_id,
                        "state": event.state_after.value,
                    }
                )
                return 0
    except (OSError, ValueError) as exc:
        parser.exit(1, f"experiment command failed: {exc}\n")
    parser.exit(2, "unknown experiment command\n")
