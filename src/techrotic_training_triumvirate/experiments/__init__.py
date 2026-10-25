"""Deterministic, restart-safe experiment orchestration without LLM control."""

from .adapters import (
    CpuDiagnosticSpec,
    PipelineAdapterError,
    assert_admission_eligible,
    run_cpu_diagnostic,
    verify_admission,
    verify_checkpoint,
    verify_corpus,
    verify_export,
    verify_training,
)
from .completion import (
    CompletionMarkerError,
    verify_completion_marker,
    write_completion_marker,
)
from .engine import Transition, advance
from .model import (
    EventKind,
    EvidenceClass,
    ExperimentContractError,
    ExperimentPlan,
    ExperimentState,
    HumanReview,
    VerifiedEvent,
)
from .qualification import CpuQ4QualificationSpec, run_cpu_q4_qualification
from .rehearsal import run_rehearsal
from .store import ExperimentStore, ExperimentStoreError, open_replayed

__all__ = [
    "CompletionMarkerError",
    "CpuDiagnosticSpec",
    "CpuQ4QualificationSpec",
    "EvidenceClass",
    "EventKind",
    "ExperimentContractError",
    "ExperimentPlan",
    "ExperimentState",
    "ExperimentStore",
    "ExperimentStoreError",
    "HumanReview",
    "PipelineAdapterError",
    "Transition",
    "VerifiedEvent",
    "advance",
    "assert_admission_eligible",
    "open_replayed",
    "run_cpu_diagnostic",
    "run_cpu_q4_qualification",
    "run_rehearsal",
    "verify_admission",
    "verify_checkpoint",
    "verify_completion_marker",
    "verify_corpus",
    "verify_export",
    "verify_training",
    "write_completion_marker",
]
