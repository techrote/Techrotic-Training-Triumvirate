"""Deterministic experiment identities and pure orchestration transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from techrotic_training_triumvirate.schemas import JsonObject, content_hash
from techrotic_training_triumvirate.training.device_admission import (
    DeviceAdmissionError,
    GPUSelection,
)


class OrchestrationError(ValueError):
    """Base error for deterministic experiment orchestration."""


class PlanValidationError(OrchestrationError):
    """An experiment plan is malformed or ambiguous."""


class TransitionError(OrchestrationError):
    """An event cannot advance the current experiment state."""


class ExperimentState(StrEnum):
    """Durable controller states from TTT-018."""

    PLANNED = "PLANNED"
    PREFLIGHT = "PREFLIGHT"
    READY = "READY"
    TRAINING = "TRAINING"
    TRAINED = "TRAINED"
    DEVELOPMENT = "DEVELOPMENT"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    EXPORTING = "EXPORTING"
    RUNTIME_QUALIFICATION = "RUNTIME_QUALIFICATION"
    FROZEN_EVALUATION = "FROZEN_EVALUATION"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    ADMISSION_READBACK = "ADMISSION_READBACK"
    COMPLETE = "COMPLETE"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    NEEDS_ENGINEERING = "NEEDS_ENGINEERING"


class EvidenceClass(StrEnum):
    """Whether evidence may participate in substantive admission."""

    ACTUAL = "actual"
    CPU_DIAGNOSTIC = "cpu_diagnostic"
    SIMULATION = "simulation"


_TERMINAL_STATES = frozenset(
    {
        ExperimentState.COMPLETE,
        ExperimentState.CANCELLED,
        ExperimentState.BUDGET_EXHAUSTED,
        ExperimentState.FAILED,
        ExperimentState.REJECTED,
        ExperimentState.NEEDS_ENGINEERING,
    }
)

_TRANSITIONS: dict[tuple[ExperimentState, str], ExperimentState] = {
    (ExperimentState.PLANNED, "PLAN_VALIDATED"): ExperimentState.PREFLIGHT,
    (ExperimentState.PREFLIGHT, "PREFLIGHT_PASSED"): ExperimentState.READY,
    (ExperimentState.READY, "WORKER_LAUNCHED"): ExperimentState.TRAINING,
    (ExperimentState.TRAINING, "TRAINING_VERIFIED"): ExperimentState.TRAINED,
    (ExperimentState.TRAINED, "DEVELOPMENT_STARTED"): ExperimentState.DEVELOPMENT,
    (
        ExperimentState.DEVELOPMENT,
        "CANDIDATE_SELECTED",
    ): ExperimentState.CANDIDATE_SELECTED,
    (
        ExperimentState.CANDIDATE_SELECTED,
        "EXPORT_STARTED",
    ): ExperimentState.EXPORTING,
    (
        ExperimentState.EXPORTING,
        "EXPORT_VERIFIED",
    ): ExperimentState.RUNTIME_QUALIFICATION,
    (
        ExperimentState.RUNTIME_QUALIFICATION,
        "RUNTIME_QUALIFIED",
    ): ExperimentState.FROZEN_EVALUATION,
    (
        ExperimentState.FROZEN_EVALUATION,
        "FROZEN_EVALUATION_PASSED",
    ): ExperimentState.WAITING_FOR_HUMAN,
    (
        ExperimentState.WAITING_FOR_HUMAN,
        "HUMAN_REVIEW_IMPORTED",
    ): ExperimentState.ADMISSION_READBACK,
    (
        ExperimentState.ADMISSION_READBACK,
        "DISPOSITION_VERIFIED",
    ): ExperimentState.COMPLETE,
    (ExperimentState.CANCELLING, "CANCELLED"): ExperimentState.CANCELLED,
}

_FAILURE_TRANSITIONS: dict[str, ExperimentState] = {
    "CANCEL_REQUESTED": ExperimentState.CANCELLING,
    "BUDGET_EXHAUSTED": ExperimentState.BUDGET_EXHAUSTED,
    "FAILED": ExperimentState.FAILED,
    "WORKER_FAILED": ExperimentState.FAILED,
    "REJECTED": ExperimentState.REJECTED,
    "NEEDS_ENGINEERING": ExperimentState.NEEDS_ENGINEERING,
}

_ACTIONS: dict[ExperimentState, tuple[str, ...]] = {
    ExperimentState.PREFLIGHT: ("run_preflight",),
    ExperimentState.READY: ("reserve_resources", "launch_training_worker"),
    ExperimentState.TRAINED: ("run_development",),
    ExperimentState.DEVELOPMENT: ("evaluate_development",),
    ExperimentState.CANDIDATE_SELECTED: ("start_export",),
    ExperimentState.EXPORTING: ("run_export",),
    ExperimentState.RUNTIME_QUALIFICATION: ("run_runtime_qualification",),
    ExperimentState.FROZEN_EVALUATION: ("run_frozen_evaluation",),
    ExperimentState.WAITING_FOR_HUMAN: ("publish_blinded_packet",),
    ExperimentState.ADMISSION_READBACK: ("verify_admission_readback",),
    ExperimentState.CANCELLING: ("cancel_owned_worker",),
}


def _sha256(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PlanValidationError(f"{field} must be a lowercase SHA-256")
    return value


def _git_sha(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PlanValidationError(f"{field} must be a full lowercase Git SHA")
    return value


def _seconds(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PlanValidationError(f"{field} must be a nonnegative integer")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise PlanValidationError(f"{field} must be a nonempty string")
    return value


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    """Immutable inputs whose canonical hash is the experiment identity."""

    source_archive_sha256: str
    semantic_commit: str
    model_identity_sha256: str
    dataset_identity_sha256: str
    profile_identity_sha256: str
    target_gpu_uuid: str
    gpu_budget_seconds: int
    cpu_budget_seconds: int
    artifact_root: str
    simulation: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise PlanValidationError("unsupported experiment plan schema version")
        _sha256(self.source_archive_sha256, field="source_archive_sha256")
        _git_sha(self.semantic_commit, field="semantic_commit")
        _sha256(self.model_identity_sha256, field="model_identity_sha256")
        _sha256(self.dataset_identity_sha256, field="dataset_identity_sha256")
        _sha256(self.profile_identity_sha256, field="profile_identity_sha256")
        _seconds(self.gpu_budget_seconds, field="gpu_budget_seconds")
        _seconds(self.cpu_budget_seconds, field="cpu_budget_seconds")
        _text(self.artifact_root, field="artifact_root")
        if not isinstance(self.simulation, bool):
            raise PlanValidationError("simulation must be boolean")
        try:
            normalized = GPUSelection.from_uuid(self.target_gpu_uuid).uuid
        except DeviceAdmissionError as exc:
            raise PlanValidationError(str(exc)) from exc
        if normalized != self.target_gpu_uuid:
            raise PlanValidationError(
                "target_gpu_uuid must use canonical GPU-UUID form"
            )

    @property
    def experiment_id(self) -> str:
        """Return the immutable content-derived experiment identity."""

        return f"ttt-exp-{content_hash(self.to_object())[:24]}"

    def to_object(self) -> JsonObject:
        return {
            "schema_version": self.schema_version,
            "source_archive_sha256": self.source_archive_sha256,
            "semantic_commit": self.semantic_commit,
            "model_identity_sha256": self.model_identity_sha256,
            "dataset_identity_sha256": self.dataset_identity_sha256,
            "profile_identity_sha256": self.profile_identity_sha256,
            "target_gpu_uuid": self.target_gpu_uuid,
            "gpu_budget_seconds": self.gpu_budget_seconds,
            "cpu_budget_seconds": self.cpu_budget_seconds,
            "artifact_root": self.artifact_root,
            "simulation": self.simulation,
        }

    @classmethod
    def from_object(cls, value: object) -> Self:
        if not isinstance(value, dict):
            raise PlanValidationError("experiment plan must be a JSON object")
        required = {
            "schema_version",
            "source_archive_sha256",
            "semantic_commit",
            "model_identity_sha256",
            "dataset_identity_sha256",
            "profile_identity_sha256",
            "target_gpu_uuid",
            "gpu_budget_seconds",
            "cpu_budget_seconds",
            "artifact_root",
            "simulation",
        }
        if set(value) != required:
            raise PlanValidationError(
                "experiment plan fields differ from the versioned schema"
            )
        schema_version = value["schema_version"]
        simulation = value["simulation"]
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise PlanValidationError("schema_version must be an integer")
        if not isinstance(simulation, bool):
            raise PlanValidationError("simulation must be boolean")
        return cls(
            source_archive_sha256=_sha256(
                value["source_archive_sha256"], field="source_archive_sha256"
            ),
            semantic_commit=_git_sha(
                value["semantic_commit"], field="semantic_commit"
            ),
            model_identity_sha256=_sha256(
                value["model_identity_sha256"], field="model_identity_sha256"
            ),
            dataset_identity_sha256=_sha256(
                value["dataset_identity_sha256"], field="dataset_identity_sha256"
            ),
            profile_identity_sha256=_sha256(
                value["profile_identity_sha256"], field="profile_identity_sha256"
            ),
            target_gpu_uuid=_text(value["target_gpu_uuid"], field="target_gpu_uuid"),
            gpu_budget_seconds=_seconds(
                value["gpu_budget_seconds"], field="gpu_budget_seconds"
            ),
            cpu_budget_seconds=_seconds(
                value["cpu_budget_seconds"], field="cpu_budget_seconds"
            ),
            artifact_root=_text(value["artifact_root"], field="artifact_root"),
            simulation=simulation,
            schema_version=schema_version,
        )


@dataclass(frozen=True, slots=True)
class Transition:
    """Pure transition result plus the next declared controller actions."""

    state: ExperimentState
    actions: tuple[str, ...]


def advance(state: ExperimentState, event_type: str) -> Transition:
    """Advance one state using only a verified typed event."""

    if state in _TERMINAL_STATES:
        raise TransitionError(f"{state} is terminal")
    if event_type in _FAILURE_TRANSITIONS and state != ExperimentState.CANCELLING:
        next_state = _FAILURE_TRANSITIONS[event_type]
        return Transition(next_state, _ACTIONS.get(next_state, ()))
    next_state = _TRANSITIONS.get((state, event_type))
    if next_state is None:
        raise TransitionError(f"{event_type} cannot advance {state}")
    return Transition(next_state, _ACTIONS.get(next_state, ()))


def semantic_stage_identity(
    plan: ExperimentPlan,
    stage: ExperimentState,
    inputs: JsonObject,
) -> str:
    """Bind a stage to immutable experiment inputs and its explicit dependencies."""

    return content_hash(
        {
            "experiment_id": plan.experiment_id,
            "stage": stage.value,
            "inputs": inputs,
        }
    )


def make_event_id(
    experiment_id: str,
    event_type: str,
    timestamp_ns: int,
    payload: JsonObject,
    *,
    idempotency_key: str | None = None,
) -> str:
    """Derive a stable event identifier for exact redelivery."""

    return content_hash(
        {
            "experiment_id": experiment_id,
            "event_type": event_type,
            "timestamp_ns": timestamp_ns,
            "payload": payload,
            "idempotency_key": idempotency_key,
        }
    )
