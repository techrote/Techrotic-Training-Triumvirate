"""Adapters from the deterministic controller into existing TTT pipeline verifiers."""

from __future__ import annotations

from pathlib import Path

from techrotic_training_triumvirate.admission import verify_package
from techrotic_training_triumvirate.schemas import JsonObject
from techrotic_training_triumvirate.training.campaign_integrity import (
    VerifiedTrainingReuse,
    verify_checkpoint_identity,
    verify_training_reuse,
)
from techrotic_training_triumvirate.training.data import load_corpus_examples
from techrotic_training_triumvirate.training.model import (
    DatasetIdentity,
    ModelBinding,
    SourceExample,
    TrainingConfig,
)

from .artifacts import verify_completion_marker
from .model import EvidenceClass
from .store import ExperimentStore


def load_verified_corpus(
    corpus_dir: str | Path,
) -> tuple[tuple[SourceExample, ...], DatasetIdentity]:
    """Reuse the existing manifest/shard/hash/split corpus validator."""

    return load_corpus_examples(corpus_dir)


def verify_resumable_checkpoint(
    directory: str | Path,
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    source_revision: str,
) -> str:
    """Reuse the existing source/model/config/data checkpoint identity gate."""

    return verify_checkpoint_identity(
        directory,
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=source_revision,
    )


def verify_completed_training(
    directory: str | Path,
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    source_revision: str,
) -> VerifiedTrainingReuse:
    """Reuse the existing native parity and artifact-inventory readback."""

    return verify_training_reuse(
        directory,
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=source_revision,
    )


def verify_stage_completion(
    directory: str | Path,
    *,
    stage_id: str,
    evidence_class: EvidenceClass,
) -> dict[str, str]:
    """Require the orchestration completion marker in addition to process exit."""

    return verify_completion_marker(
        directory,
        expected_stage_id=stage_id,
        expected_evidence_class=evidence_class,
    )


def verify_actual_admission(
    store: ExperimentStore,
    experiment_id: str,
    package: str | Path,
    *,
    evidence_root: str | Path,
) -> JsonObject:
    """Run the existing strict admission verifier only across actual evidence.

    Simulation evidence is rejected before the package verifier is called.
    CPU diagnostics may coexist but can never substitute for actual evidence.
    """

    store.assert_actual_evidence(experiment_id)
    return verify_package(package, evidence_root=evidence_root)
