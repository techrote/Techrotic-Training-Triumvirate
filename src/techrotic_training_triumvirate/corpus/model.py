"""Corpus assembly records and configuration.

These records are derived views over canonical episode schemas. They are not added to
the durable schema registry because corpus manifests and shards are generated artifacts
whose identity is defined by canonical JSON plus SHA-256 hashes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from techrotic_training_triumvirate.schemas import (
    EpisodeRecord,
    JsonObject,
    SourceProvenance,
)


class CorpusTier(str, Enum):
    """Admitted corpus tiers implemented by TTT-007."""

    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class CorpusSplit(str, Enum):
    """Dataset partitions emitted by the assembler."""

    TRAIN = "train"
    DEV = "dev"
    FROZEN_EVAL = "frozen_eval"


@dataclass(frozen=True, slots=True)
class TeacherEnrichment:
    """Accepted teacher material attached to one canonical turn."""

    source_id: str
    turn_id: int
    operational_facts: JsonObject
    style_text: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("teacher enrichment source_id must not be empty")
        if self.turn_id < 0:
            raise ValueError("teacher enrichment turn_id must be non-negative")
        if self.style_text is not None and not self.style_text.strip():
            raise ValueError("teacher enrichment style_text must be null or non-empty")


@dataclass(frozen=True, slots=True)
class CorpusSource:
    """One candidate episode plus its provenance and accepted enrichments."""

    episode: EpisodeRecord
    tier: CorpusTier
    provenance: tuple[SourceProvenance, ...]
    teacher_enrichments: tuple[TeacherEnrichment, ...] = ()


@dataclass(frozen=True, slots=True)
class CorpusConfig:
    """Deterministic split and shard policy."""

    seed: int = 0
    dev_percent: int = 20
    shard_size: int = 1024
    frozen_scenario_ids: frozenset[str] = field(default_factory=frozenset)
    frozen_families: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not 0 <= self.dev_percent <= 100:
            raise ValueError("dev_percent must be between 0 and 100")
        if self.shard_size < 1:
            raise ValueError("shard_size must be positive")


@dataclass(frozen=True, slots=True)
class CorpusIssue:
    """Stable machine-readable validation or rejection reason."""

    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class QuarantinedSource:
    """Source refused from admitted corpus output."""

    episode_id: str
    issues: tuple[CorpusIssue, ...]


@dataclass(frozen=True, slots=True)
class CorpusExample:
    """One deterministic supervised example."""

    example_id: str
    split: CorpusSplit
    tier: CorpusTier
    episode_id: str
    scenario_id: str
    scenario_family: str
    persona_id: str
    turn_id: int
    mode: str
    input: JsonObject
    target: JsonObject
    provenance_refs: tuple[str, ...]
    teacher_source_ids: tuple[str, ...]

    def to_object(self) -> JsonObject:
        return {
            "example_id": self.example_id,
            "split": self.split.value,
            "tier": self.tier.value,
            "episode_id": self.episode_id,
            "scenario_id": self.scenario_id,
            "scenario_family": self.scenario_family,
            "persona_id": self.persona_id,
            "turn_id": self.turn_id,
            "mode": self.mode,
            "input": self.input,
            "target": self.target,
            "provenance_refs": list(self.provenance_refs),
            "teacher_source_ids": list(self.teacher_source_ids),
        }


@dataclass(frozen=True, slots=True)
class CorpusShard:
    """Inspectable deterministic JSONL shard."""

    name: str
    split: CorpusSplit
    line_count: int
    sha256: str
    content: str


@dataclass(frozen=True, slots=True)
class CorpusBuild:
    """Complete in-memory corpus build result."""

    examples: tuple[CorpusExample, ...]
    shards: tuple[CorpusShard, ...]
    quarantine: tuple[QuarantinedSource, ...]
    manifest: JsonObject
