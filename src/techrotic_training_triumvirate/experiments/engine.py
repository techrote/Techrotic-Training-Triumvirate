"""Pure deterministic state transitions for admitted experiment plans."""

from __future__ import annotations

from dataclasses import dataclass

from .model import EventKind, ExperimentContractError, ExperimentState, VerifiedEvent


@dataclass(frozen=True, slots=True)
class Transition:
    state: ExperimentState
    actions: tuple[str, ...]


_TRANSITIONS: dict[tuple[ExperimentState, EventKind], Transition] = {
    (ExperimentState.PLANNED, EventKind.PLAN_VALIDATED): Transition(
        ExperimentState.PREFLIGHT, ("run_preflight",)
    ),
    (ExperimentState.PREFLIGHT, EventKind.PREFLIGHT_PASSED): Transition(
        ExperimentState.READY, ("reserve_resources",)
    ),
    (ExperimentState.READY, EventKind.WORKER_LAUNCHED): Transition(
        ExperimentState.TRAINING, ("watch_worker",)
    ),
    (ExperimentState.TRAINING, EventKind.TRAINING_VERIFIED): Transition(
        ExperimentState.TRAINED, ("start_development",)
    ),
    # A pause request fences downstream actions even if training is still running.
    (ExperimentState.TRAINING, EventKind.PAUSE_REQUESTED): Transition(
        ExperimentState.PAUSING, ("fence_downstream", "await_trained_boundary")
    ),
    (ExperimentState.TRAINED, EventKind.PAUSE_REQUESTED): Transition(
        ExperimentState.PAUSING, ("fence_downstream", "verify_quiescence")
    ),
    (ExperimentState.PAUSING, EventKind.TRAINING_VERIFIED): Transition(
        ExperimentState.PAUSING, ("verify_quiescence",)
    ),
    (ExperimentState.PAUSING, EventKind.PAUSE_CONFIRMED): Transition(
        ExperimentState.PAUSED, ("preserve_evidence",)
    ),
    # Unpausing does not launch work. The next development step remains explicit.
    (ExperimentState.PAUSED, EventKind.RESUME_REQUESTED): Transition(
        ExperimentState.TRAINED, ("verify_training_reuse_before_development",)
    ),
    (ExperimentState.TRAINED, EventKind.DEVELOPMENT_STARTED): Transition(
        ExperimentState.DEVELOPMENT, ("evaluate_development",)
    ),
    (ExperimentState.DEVELOPMENT, EventKind.DEVELOPMENT_PASSED): Transition(
        ExperimentState.CANDIDATE_SELECTED, ("start_export",)
    ),
    (ExperimentState.CANDIDATE_SELECTED, EventKind.EXPORT_STARTED): Transition(
        ExperimentState.EXPORTING, ("verify_export",)
    ),
    (ExperimentState.EXPORTING, EventKind.EXPORT_VERIFIED): Transition(
        ExperimentState.RUNTIME_QUALIFICATION, ("qualify_runtime",)
    ),
    (ExperimentState.RUNTIME_QUALIFICATION, EventKind.RUNTIME_PASSED): Transition(
        ExperimentState.FROZEN_EVALUATION, ("run_frozen_evaluation",)
    ),
    (ExperimentState.FROZEN_EVALUATION, EventKind.FROZEN_PASSED): Transition(
        ExperimentState.WAITING_FOR_HUMAN, ("prepare_blinded_packet",)
    ),
    (ExperimentState.WAITING_FOR_HUMAN, EventKind.HUMAN_REVIEW_IMPORTED): Transition(
        ExperimentState.ADMISSION_READBACK, ("verify_admission",)
    ),
    (ExperimentState.ADMISSION_READBACK, EventKind.ADMISSION_VERIFIED): Transition(
        ExperimentState.COMPLETE, ("seal_evidence",)
    ),
    (ExperimentState.CANCELLING, EventKind.CANCELLED): Transition(
        ExperimentState.CANCELLED, ("preserve_evidence", "release_resources")
    ),
}

_ACTIVE = frozenset(
    {
        ExperimentState.PLANNED,
        ExperimentState.PREFLIGHT,
        ExperimentState.READY,
        ExperimentState.TRAINING,
        ExperimentState.TRAINED,
        ExperimentState.PAUSING,
        ExperimentState.PAUSED,
        ExperimentState.DEVELOPMENT,
        ExperimentState.CANDIDATE_SELECTED,
        ExperimentState.EXPORTING,
        ExperimentState.RUNTIME_QUALIFICATION,
        ExperimentState.FROZEN_EVALUATION,
        ExperimentState.WAITING_FOR_HUMAN,
        ExperimentState.ADMISSION_READBACK,
    }
)
_FAILURES: dict[EventKind, ExperimentState] = {
    EventKind.CANCEL_REQUESTED: ExperimentState.CANCELLING,
    EventKind.BUDGET_EXHAUSTED: ExperimentState.BUDGET_EXHAUSTED,
    EventKind.FAILED: ExperimentState.FAILED,
    EventKind.REJECTED: ExperimentState.REJECTED,
    EventKind.ENGINEERING_REQUIRED: ExperimentState.NEEDS_ENGINEERING,
}


def advance(state: ExperimentState, event: VerifiedEvent) -> Transition:
    """Advance only through declared events; prose/log contents never drive state."""

    failure_state = _FAILURES.get(event.kind)
    if failure_state is not None and state in _ACTIVE:
        return Transition(failure_state, ("preserve_evidence", "release_resources"))

    transition = _TRANSITIONS.get((state, event.kind))
    if transition is None:
        raise ExperimentContractError(
            f"event {event.kind.value} is invalid from state {state.value}"
        )
    return transition
