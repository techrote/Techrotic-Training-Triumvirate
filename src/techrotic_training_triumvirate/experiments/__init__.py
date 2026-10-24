"""Deterministic, restart-safe experiment orchestration without LLM control."""

from .adapters import (
    CpuDiagnosticSpec,
    PipelineAdapterError,
    assert_admission_eligible,
    run_cpu_diagnostic,
    verify_admission,
    verify_corpus,
    verify_export,
    verify_training,
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
from .rehearsal import run_rehearsal
from .store import ExperimentStore, ExperimentStoreError, open_replayed

__all__ = [
    "CpuDiagnosticSpec",
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
    "run_rehearsal",
    "verify_admission",
    "verify_corpus",
    "verify_export",
    "verify_training",
]
