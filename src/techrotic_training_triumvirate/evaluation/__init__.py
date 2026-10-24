"""Frozen model-agnostic evaluation harness, baselines, reports, and guards."""

from .baselines import ScriptedCommanderBaseline, WeakCommanderBaseline
from .guard import (
    FrozenEvaluationGuard,
    FrozenEvaluationGuardError,
    FrozenReservation,
    frozen_evaluation_guard,
)
from .model import (
    BenchmarkCase,
    BenchmarkManifest,
    BenchmarkReport,
    CaseResult,
    EvaluationContext,
    PolicyIdentity,
    StudentAdapter,
)
from .runner import run_benchmark
from .suite import (
    BENCHMARK_RESOURCE,
    EXPECTED_BENCHMARK_HASH,
    BenchmarkIntegrityError,
    load_benchmark_v1,
)

__all__ = [
    "BENCHMARK_RESOURCE",
    "EXPECTED_BENCHMARK_HASH",
    "BenchmarkCase",
    "BenchmarkIntegrityError",
    "BenchmarkManifest",
    "BenchmarkReport",
    "CaseResult",
    "EvaluationContext",
    "FrozenEvaluationGuard",
    "FrozenEvaluationGuardError",
    "FrozenReservation",
    "PolicyIdentity",
    "ScriptedCommanderBaseline",
    "StudentAdapter",
    "WeakCommanderBaseline",
    "frozen_evaluation_guard",
    "load_benchmark_v1",
    "run_benchmark",
]
