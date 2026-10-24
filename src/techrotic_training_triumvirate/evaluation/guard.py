"""Frozen evaluation reservation guard for corpus/corrective-rollout consumers."""

from __future__ import annotations

from dataclasses import dataclass

from .model import BenchmarkManifest
from .suite import load_benchmark_v1


class FrozenEvaluationGuardError(ValueError):
    """Raised when training/corrective data collides with a frozen evaluation case."""


@dataclass(frozen=True, slots=True)
class FrozenReservation:
    case_id: str
    family: str
    seed: int


@dataclass(frozen=True, slots=True)
class FrozenEvaluationGuard:
    """Exact family/seed blacklist derived from an immutable benchmark manifest."""

    benchmark_id: str
    benchmark_version: str
    benchmark_hash: str
    reservations: tuple[FrozenReservation, ...]

    @classmethod
    def from_manifest(cls, manifest: BenchmarkManifest) -> FrozenEvaluationGuard:
        return cls(
            benchmark_id=manifest.benchmark_id,
            benchmark_version=manifest.benchmark_version,
            benchmark_hash=manifest.manifest_hash,
            reservations=tuple(
                FrozenReservation(
                    case_id=case.case_id,
                    family=case.family,
                    seed=case.seed,
                )
                for case in manifest.cases
            ),
        )

    def case_for(self, *, family: str, seed: int) -> str | None:
        for reservation in self.reservations:
            if reservation.family == family and reservation.seed == seed:
                return reservation.case_id
        return None

    def is_reserved(self, *, family: str, seed: int) -> bool:
        return self.case_for(family=family, seed=seed) is not None

    def assert_training_allowed(self, *, family: str, seed: int) -> None:
        case_id = self.case_for(family=family, seed=seed)
        if case_id is not None:
            raise FrozenEvaluationGuardError(
                "scenario is reserved for frozen evaluation and must not enter "
                f"training/corrective corpora: {case_id} ({family}, seed={seed})"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "benchmark_hash": self.benchmark_hash,
            "reservations": [
                {
                    "case_id": item.case_id,
                    "family": item.family,
                    "seed": item.seed,
                }
                for item in self.reservations
            ],
        }


def frozen_evaluation_guard() -> FrozenEvaluationGuard:
    """Return the guard TTT-007/TTT-010 must consume before admitting data."""
    return FrozenEvaluationGuard.from_manifest(load_benchmark_v1())
