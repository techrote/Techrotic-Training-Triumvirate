"""TTT-012 reproducible training/export acceptance tests."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from techrotic_training_triumvirate.model_admission import load_model_cast_v1
from techrotic_training_triumvirate.schemas import canonical_json
from techrotic_training_triumvirate.training import (
    DatasetIdentity,
    TinyTrainingError,
    TrainingAdmissionError,
    TrainingDataError,
    TrainingMix,
    authorize_heavy_training,
    dataset_identity_from_examples,
    export_tiny,
    load_corpus_examples,
    load_training_config,
    map_dataset,
    map_source_example,
    quantization_export_spec,
    resolve_model_binding,
    smoke_source_examples,
    train_tiny,
    validate_assistant_target,
)
from techrotic_training_triumvirate.training.cli import main as training_main
from techrotic_training_triumvirate.training.hf_peft import tokenize_for_causal_lm


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_model_bindings_and_profiles_resolve_from_admission() -> None:
    cast = load_model_cast_v1()
    primary_key = cast["roles"]["primary_compact_student"]
    challenger_key = cast["roles"]["challenger_students"][0]

    primary = resolve_model_binding("primary")
    challenger = resolve_model_binding("challenger")
    assert primary.model_key == primary_key
    assert challenger.model_key == challenger_key
    assert primary.native_repository == cast["models"][primary_key]["native"]["repository"]
    assert challenger.native_revision == cast["models"][challenger_key]["native"]["revision"]

    primary_config = load_training_config("primary")
    challenger_config = load_training_config("challenger")
    assert primary_config.method == "lora"
    assert challenger_config.method == "lora"
    assert primary_config.backend == "hf-transformers-peft"
    assert challenger_config.backend == "hf-transformers-peft"


def test_mapping_keeps_authoritative_feedback_in_input_only() -> None:
    sources = smoke_source_examples()
    recovery = next(item for item in sources if item.mode == "recovery")
    mapped = map_source_example(recovery, mix=TrainingMix.JOINT_CORRECTIVE)
    assert mapped is not None
    user_message = mapped.prompt_messages[-1].content
    assert "ttt.interpreter_result" in user_message
    assert "ttt.interpreter_result" not in mapped.assistant_target
    assert "world_events" not in mapped.assistant_target

    bad = copy.deepcopy(recovery.target)
    bad["interpreter_results"] = []
    with pytest.raises(TrainingDataError):
        validate_assistant_target(bad)

    nested = copy.deepcopy(recovery.target)
    nested["commands"] = [
        {
            "schema": "ttt.interpreter_result",
            "schema_version": 1,
            "payload": {},
        }
    ]
    with pytest.raises(TrainingDataError):
        validate_assistant_target(nested)


def test_dataset_mix_semantics() -> None:
    sources = smoke_source_examples()

    operational = map_dataset(sources, mix=TrainingMix.OPERATIONAL)
    assert operational
    for item in operational:
        target = json.loads(item.assistant_target)
        assert target["communications"] == []

    persona = map_dataset(sources, mix=TrainingMix.PERSONA)
    assert persona
    for item in persona:
        target = json.loads(item.assistant_target)
        assert target["commands"] == []

    joint = map_dataset(sources, mix=TrainingMix.JOINT)
    assert {item.example_id for item in joint} == {
        "smoke-001",
        "smoke-002",
        "smoke-003",
    }

    corrective = map_dataset(sources, mix=TrainingMix.JOINT_CORRECTIVE)
    assert {item.example_id for item in corrective} == {
        "smoke-001",
        "smoke-002",
        "smoke-003",
        "smoke-004",
    }


def test_smoke_training_is_seeded_resumable_and_train_split_only(
    tmp_path: Path,
) -> None:
    sources = smoke_source_examples()
    dataset = dataset_identity_from_examples(sources)
    mapped = map_dataset(sources, mix=TrainingMix.JOINT_CORRECTIVE)
    binding = resolve_model_binding("primary")
    config = load_training_config(
        "primary",
        mix=TrainingMix.JOINT_CORRECTIVE,
        seed=24301,
    )

    partial_path = tmp_path / "partial.json"
    partial = train_tiny(
        mapped,
        binding=binding,
        config=config,
        dataset=dataset,
        checkpoint_path=partial_path,
        max_steps=1,
    )
    assert not partial.complete
    resumed = train_tiny(
        mapped,
        binding=binding,
        config=config,
        dataset=dataset,
        checkpoint_path=partial_path,
        resume=True,
    )
    uninterrupted = train_tiny(
        mapped,
        binding=binding,
        config=config,
        dataset=dataset,
        checkpoint_path=tmp_path / "full.json",
    )
    assert resumed.complete
    assert resumed.model_hash == uninterrupted.model_hash
    assert resumed.memory == uninterrupted.memory
    assert "smoke-003" not in resumed.ordered_example_ids
    assert set(resumed.ordered_example_ids) == {
        "smoke-001",
        "smoke-002",
        "smoke-004",
    }

    changed_dataset = DatasetIdentity(
        manifest_sha256="0" * 64,
        dataset_hash=dataset.dataset_hash,
        shard_hashes=dataset.shard_hashes,
        split_identity=dataset.split_identity,
    )
    with pytest.raises(TinyTrainingError):
        train_tiny(
            mapped,
            binding=binding,
            config=config,
            dataset=changed_dataset,
            checkpoint_path=partial_path,
            resume=True,
        )


def test_export_roundtrip_emits_complete_manifest_and_parity(tmp_path: Path) -> None:
    sources = smoke_source_examples()
    dataset = dataset_identity_from_examples(sources)
    mapped = map_dataset(sources, mix=TrainingMix.JOINT_CORRECTIVE)
    binding = resolve_model_binding("primary")
    config = load_training_config(
        "primary",
        mix=TrainingMix.JOINT_CORRECTIVE,
        seed=24301,
    )
    trained = train_tiny(
        mapped,
        binding=binding,
        config=config,
        dataset=dataset,
        checkpoint_path=tmp_path / "checkpoint.json",
    )
    export_dir = tmp_path / "export"
    manifest = export_tiny(
        trained,
        mapped,
        binding=binding,
        config=config,
        dataset=dataset,
        output_dir=export_dir,
        git_commit="test-head",
    )

    assert manifest["parity"]["passed"] is True
    assert manifest["dataset_identity"]["manifest_sha256"] == dataset.manifest_sha256
    assert manifest["base_model_identity"]["native_revision"] == binding.native_revision
    assert (export_dir / "adapter.json").is_file()
    assert (export_dir / "run-manifest.json").is_file()
    assert (export_dir / "export-manifest.json").is_file()

    run = json.loads((export_dir / "run-manifest.json").read_text(encoding="utf-8"))
    assert run["schema"] == "ttt.run_manifest"
    assert run["payload"]["generator_config"]["dataset_identity"]["dataset_hash"] == (
        dataset.dataset_hash
    )
    assert run["payload"]["runtime"]["heavy_training"] is False


def test_corpus_loader_verifies_manifest_and_shards(tmp_path: Path) -> None:
    sources = smoke_source_examples()
    train_sources = [item for item in sources if item.split == "train"]
    dev_sources = [item for item in sources if item.split == "dev"]
    train_content = "".join(
        f"{canonical_json(item.to_object())}\n" for item in train_sources
    )
    dev_content = "".join(
        f"{canonical_json(item.to_object())}\n" for item in dev_sources
    )
    (tmp_path / "train-00000.jsonl").write_text(train_content, encoding="utf-8")
    (tmp_path / "dev-00000.jsonl").write_text(dev_content, encoding="utf-8")
    manifest = {
        "manifest_version": 1,
        "split_identity": {"train": "train-id", "dev": "dev-id"},
        "shards": [
            {
                "name": "train-00000.jsonl",
                "split": "train",
                "line_count": len(train_sources),
                "sha256": _sha(train_content),
            },
            {
                "name": "dev-00000.jsonl",
                "split": "dev",
                "line_count": len(dev_sources),
                "sha256": _sha(dev_content),
            },
        ],
    }
    raw_manifest = f"{canonical_json(manifest)}\n"
    (tmp_path / "manifest.json").write_text(raw_manifest, encoding="utf-8")

    loaded, identity = load_corpus_examples(tmp_path)
    assert {item.example_id for item in loaded} == {
        item.example_id for item in sources
    }
    assert identity.manifest_sha256 == _sha(raw_manifest)
    assert dict(identity.shard_hashes)["train-00000.jsonl"] == _sha(train_content)

    (tmp_path / "train-00000.jsonl").write_text(
        f"{train_content}tampered\n",
        encoding="utf-8",
    )
    with pytest.raises(TrainingDataError, match="SHA-256 mismatch"):
        load_corpus_examples(tmp_path)


def test_heavy_training_requires_explicit_bounded_admission() -> None:
    with pytest.raises(TrainingAdmissionError, match="opt-in"):
        authorize_heavy_training(
            gpu_hours=1.0,
            external_compute_cost_gbp=1.0,
            opt_in=False,
        )
    with pytest.raises(TrainingAdmissionError, match="exceeds TTT-012"):
        authorize_heavy_training(
            gpu_hours=3.01,
            external_compute_cost_gbp=1.0,
            opt_in=True,
        )
    admitted = authorize_heavy_training(
        gpu_hours=1.0,
        external_compute_cost_gbp=5.0,
        opt_in=True,
    )
    assert admitted.gpu_hours == 1.0
    assert admitted.paid_model_api_cost_gbp == 0.0


def test_quantization_is_opt_in_and_bound_to_admitted_runtime() -> None:
    spec = quantization_export_spec("primary")
    cast = load_model_cast_v1()
    primary_key = cast["roles"]["primary_compact_student"]
    assert spec["enabled_by_default"] is False
    assert spec["format"] == "GGUF"
    assert spec["type"] == "Q4_K_M"
    assert spec["runtime_revision"] == cast["probe_defaults"]["runtime_revision"]
    assert spec["reference_inference_artifact_sha256"] == (
        cast["models"][primary_key]["inference"]["artifact_sha256"]
    )


class _FakeTokenizer:
    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> list[int]:
        assert tokenize
        if add_generation_prompt:
            return [10, 20, 30]
        assert messages[-1]["role"] == "assistant"
        return [10, 20, 30, 40, 50]


def test_native_template_tokenization_masks_prompt_from_loss() -> None:
    mapped = map_dataset(
        smoke_source_examples(),
        mix=TrainingMix.JOINT_CORRECTIVE,
    )[0]
    encoded = tokenize_for_causal_lm(
        _FakeTokenizer(),
        mapped,
        max_sequence_tokens=32,
    )
    assert encoded["input_ids"] == [10, 20, 30, 40, 50]
    assert encoded["labels"] == [-100, -100, -100, 40, 50]


def test_training_cli_profile_and_smoke(tmp_path: Path, capsys: Any) -> None:
    assert training_main(["profile", "--model", "primary"]) == 0
    profile_output = json.loads(capsys.readouterr().out)
    assert profile_output["training_config"]["method"] == "lora"

    output = tmp_path / "smoke"
    assert (
        training_main(
            [
                "smoke",
                "--model",
                "primary",
                "--mix",
                "joint+corrective",
                "--output",
                str(output),
                "--git-commit",
                "test-head",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["parity"]["passed"] is True
    assert (output / "export" / "run-manifest.json").is_file()
