"""Public model-agnostic evaluation contracts for TTT benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommanderObservation,
    InterpreterResult,
    JsonObject,
    PersonaSpec,
    canonical_json,
    content_hash,
)


@dataclass(frozen=True, slots=True)
class PolicyIdentity:
    """Stable identity bound into every benchmark report."""

    policy_id: str
    adapter_id: str
    revision: str

    def __post_init__(self) -> None:
        for name, value in (
            ("policy_id", self.policy_id),
            ("adapter_id", self.adapter_id),
            ("revision", self.revision),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "adapter_id": self.adapter_id,
            "revision": self.revision,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One immutable generated or handwritten/adversarial benchmark case."""

    case_id: str
    suite: str
    kind: str
    family: str
    seed: int
    complexity: int
    unit_count: int
    mid_state: bool
    turns: int

    def __post_init__(self) -> None:
        if self.suite not in {"generated", "adversarial"}:
            raise ValueError("suite must be generated or adversarial")
        if not self.case_id.strip() or not self.kind.strip() or not self.family.strip():
            raise ValueError("case identity fields must not be empty")
        if self.turns < 1:
            raise ValueError("turns must be positive")


@dataclass(frozen=True, slots=True)
class BenchmarkManifest:
    """Parsed, integrity-checked immutable benchmark definition."""

    benchmark_id: str
    benchmark_version: str
    manifest_hash: str
    generated: tuple[BenchmarkCase, ...]
    adversarial: tuple[BenchmarkCase, ...]
    persona: PersonaSpec

    @property
    def cases(self) -> tuple[BenchmarkCase, ...]:
        return self.generated + self.adversarial


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Admitted per-turn surface presented to a StudentAdapter."""

    case_id: str
    turn_index: int
    observation_generation: int
    observation: CommanderObservation
    structured_observation: JsonObject
    compact_observation: str
    previous_results: tuple[InterpreterResult, ...]
    recent_events: tuple[AuthoritativeEvent, ...]
    persona: PersonaSpec


class StudentAdapter(Protocol):
    """Model-independent policy contract consumed by the benchmark runner."""

    @property
    def identity(self) -> PolicyIdentity: ...

    def begin_case(self, *, case_id: str, seed: int) -> None: ...

    def act(self, context: EvaluationContext) -> AssistantAction: ...


@dataclass(frozen=True, slots=True)
class CaseResult:
    """Deterministic compact result for one benchmark case."""

    case_id: str
    suite: str
    kind: str
    command_count: int
    communication_count: int
    accepted_count: int
    rejected_count: int
    metrics: dict[str, float]
    violations: dict[str, int]
    final_state_hash: str
    event_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "suite": self.suite,
            "kind": self.kind,
            "command_count": self.command_count,
            "communication_count": self.communication_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "metrics": dict(sorted(self.metrics.items())),
            "violations": dict(sorted(self.violations.items())),
            "final_state_hash": self.final_state_hash,
            "event_hash": self.event_hash,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Machine- and human-readable deterministic benchmark report."""

    benchmark_id: str
    benchmark_version: str
    benchmark_hash: str
    code_revision: str
    policy: PolicyIdentity
    cases: tuple[CaseResult, ...]
    operational: dict[str, object]
    character: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "benchmark_id": self.benchmark_id,
            "benchmark_version": self.benchmark_version,
            "benchmark_hash": self.benchmark_hash,
            "code_revision": self.code_revision,
            "policy": self.policy.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
            "operational": self.operational,
            "character": self.character,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def report_hash(self) -> str:
        return content_hash(self.to_dict())

    def to_markdown(self) -> str:
        mechanical = self.operational.get("mechanical", {})
        closed_loop = self.operational.get("closed_loop", {})
        hidden = self.operational.get("hidden_information", {})
        proxies = self.character.get("automated_proxies", {})
        human_value = self.character.get("human_evaluation_required", ())
        human = human_value if isinstance(human_value, (list, tuple)) else ()
        lines = [
            f"# Benchmark report — {self.benchmark_id} v{self.benchmark_version}",
            "",
            f"- Benchmark hash: `{self.benchmark_hash}`",
            f"- Report hash: `{self.report_hash()}`",
            f"- Code revision: `{self.code_revision}`",
            f"- Policy: `{self.policy.policy_id}` / `{self.policy.revision}`",
            "",
            "## Operational competence",
            "",
            f"- Mechanical: `{canonical_json(mechanical)}`",
            f"- Closed loop: `{canonical_json(closed_loop)}`",
            f"- Hidden information: `{canonical_json(hidden)}`",
            "",
            "## Character proxies",
            "",
            f"- Automated: `{canonical_json(proxies)}`",
            f"- Human evaluation required: {', '.join(str(item) for item in human)}",
            "",
            "Operational competence and character proxies are reported separately.",
        ]
        return "\n".join(lines) + "\n"
