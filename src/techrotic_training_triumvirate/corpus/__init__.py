"""Validated, provenance-rich deterministic corpus assembly."""

from .assembler import assemble_corpus, validate_source, write_corpus
from .model import (
    CorpusBuild,
    CorpusConfig,
    CorpusExample,
    CorpusIssue,
    CorpusShard,
    CorpusSource,
    CorpusSplit,
    CorpusTier,
    QuarantinedSource,
    TeacherEnrichment,
)

__all__ = [
    "CorpusBuild",
    "CorpusConfig",
    "CorpusExample",
    "CorpusIssue",
    "CorpusShard",
    "CorpusSource",
    "CorpusSplit",
    "CorpusTier",
    "QuarantinedSource",
    "TeacherEnrichment",
    "assemble_corpus",
    "validate_source",
    "write_corpus",
]
