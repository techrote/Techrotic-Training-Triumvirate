"""Reproducible training, export, and inference-parity machinery."""

from .admission import (
    TrainingAdmissionError,
    authorize_heavy_training,
    load_training_config,
    quantization_export_spec,
    resolve_model_binding,
    training_config_hash,
)
from .data import (
    TrainingDataError,
    dataset_identity_from_examples,
    load_corpus_examples,
    map_dataset,
    map_source_example,
    smoke_source_examples,
    source_example_from_corpus,
    validate_assistant_target,
)
from .export import TrainingExportError, build_run_manifest, export_tiny
from .model import (
    BudgetAuthorization,
    ChatMessage,
    DatasetIdentity,
    MappedExample,
    ModelBinding,
    SourceExample,
    TinyTrainingResult,
    TrainingConfig,
    TrainingMix,
)
from .tiny import TinyTrainingError, predict_tiny, render_prompt, train_tiny

__all__ = [
    "BudgetAuthorization",
    "ChatMessage",
    "DatasetIdentity",
    "MappedExample",
    "ModelBinding",
    "SourceExample",
    "TinyTrainingError",
    "TinyTrainingResult",
    "TrainingAdmissionError",
    "TrainingConfig",
    "TrainingDataError",
    "TrainingExportError",
    "TrainingMix",
    "authorize_heavy_training",
    "build_run_manifest",
    "dataset_identity_from_examples",
    "export_tiny",
    "load_corpus_examples",
    "load_training_config",
    "map_dataset",
    "map_source_example",
    "predict_tiny",
    "quantization_export_spec",
    "render_prompt",
    "resolve_model_binding",
    "smoke_source_examples",
    "source_example_from_corpus",
    "train_tiny",
    "training_config_hash",
    "validate_assistant_target",
]
