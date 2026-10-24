"""Completed-candidate resume identity regression tests, with inert fixtures only."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from techrotic_training_triumvirate.schemas import canonical_json
from techrotic_training_triumvirate.training import (
    DatasetIdentity,
    TrainingMix,
    load_training_config,
    resolve_model_binding,
)
from techrotic_training_triumvirate.training.campaign_integrity import (
    CampaignIntegrityError,
    expected_training_identity,
    verify_training_reuse,
)
from techrotic_training_triumvirate.training.export import (
    build_run_manifest,
    sha256_file,
)
from techrotic_training_triumvirate.training.model import BudgetAuthorization

SOURCE = "11e70686b09a27cf7c784beaf8d7a46717b345a0"


def _write(path: Path, value: object) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _dataset() -> DatasetIdentity:
    return DatasetIdentity("a" * 64, "b" * 64, (("train.jsonl", "c" * 64),), {})


@pytest.fixture
def completed_run(tmp_path: Path) -> Path:
    binding = resolve_model_binding("primary")
    config = load_training_config("primary", mix=TrainingMix.OPERATIONAL)
    dataset = _dataset()
    _write(
        tmp_path / "training-identity.json",
        expected_training_identity(
            binding=binding,
            config=config,
            dataset=dataset,
        ),
    )
    parity = {"schema_version": 1, "passed": True, "cases": [{"equal": True}]}
    _write(tmp_path / "parity.json", parity)
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_model.safetensors").write_bytes(
        b"inert test fixture, not weights"
    )
    hashes = {
        name: sha256_file(tmp_path / name)
        for name in (
            "training-identity.json",
            "parity.json",
            "adapter/adapter_model.safetensors",
        )
    }
    manifest = build_run_manifest(
        phase="train-export",
        binding=binding,
        config=config,
        dataset=dataset,
        git_commit=SOURCE,
        artifact_hashes=hashes,
        backend=config.backend,
        budget=BudgetAuthorization(0.1, 0.0, 0.0),
        command_line=("test-fixture",),
        extra_runtime={
            "parity_passed": True,
            "training_identity": str(
                expected_training_identity(
                    binding=binding, config=config, dataset=dataset
                )["training_identity"]
            ),
        },
    )
    _write(tmp_path / "run-manifest.json", manifest.to_dict())
    _write(
        tmp_path / "training-result.json",
        {
            "run_id": manifest.run_id,
            "run_manifest_sha256": sha256_file(tmp_path / "run-manifest.json"),
            "adapter_dir": str(adapter),
            "artifact_hashes": hashes,
            "parity": parity,
        },
    )
    return tmp_path


def _verify(root: Path, **overrides: object) -> object:
    kwargs = {
        "binding": resolve_model_binding("primary"),
        "config": load_training_config("primary", mix=TrainingMix.OPERATIONAL),
        "dataset": _dataset(),
        "source_revision": SOURCE,
    }
    kwargs.update(overrides)
    return verify_training_reuse(root, **kwargs)  # type: ignore[arg-type]


def _rewrite_manifest(root: Path, manifest: dict[str, object]) -> None:
    _write(root / "run-manifest.json", manifest)
    result = json.loads((root / "training-result.json").read_text())
    result["run_manifest_sha256"] = sha256_file(root / "run-manifest.json")
    _write(root / "training-result.json", result)


def test_exact_completed_identity_is_reusable_without_heavy_imports(
    completed_run: Path,
) -> None:
    verified = _verify(completed_run)
    assert verified is not None


def test_completed_v2_identity_is_supported_alongside_historical_v1(
    completed_run: Path,
) -> None:
    identity = expected_training_identity(
        binding=resolve_model_binding("primary"),
        config=load_training_config("primary", mix=TrainingMix.OPERATIONAL),
        dataset=_dataset(),
        source_revision=SOURCE,
    )
    _write(completed_run / "training-identity.json", identity)
    manifest = json.loads((completed_run / "run-manifest.json").read_text())
    manifest["payload"]["artifact_hashes"]["training-identity.json"] = sha256_file(
        completed_run / "training-identity.json"
    )
    manifest["payload"]["runtime"]["training_identity"] = identity["training_identity"]
    result = json.loads((completed_run / "training-result.json").read_text())
    result["artifact_hashes"] = manifest["payload"]["artifact_hashes"]
    _write(completed_run / "training-result.json", result)
    _rewrite_manifest(completed_run, manifest)
    assert _verify(completed_run) is not None


@pytest.mark.parametrize(
    "mix", [TrainingMix.PERSONA, TrainingMix.JOINT, TrainingMix.JOINT_CORRECTIVE]
)
def test_completed_adapter_cannot_be_relabelled_as_another_mix(
    completed_run: Path, mix: TrainingMix
) -> None:
    with pytest.raises(CampaignIntegrityError, match="model/config/dataset"):
        _verify(completed_run, config=load_training_config("primary", mix=mix))


def test_worker_checks_completed_mix_before_constructing_any_model(
    completed_run: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from techrotic_training_triumvirate.training.campaign import run_variant_worker

    monkeypatch.setattr(
        "techrotic_training_triumvirate.training.campaign.load_corpus_examples",
        lambda path: ((), _dataset()),
    )

    def no_model(*args: object, **kwargs: object) -> object:
        raise AssertionError("mismatched completed artifact reached model loading")

    monkeypatch.setattr(
        "techrotic_training_triumvirate.training.campaign.HFStudentAdapter",
        no_model,
    )
    with pytest.raises(CampaignIntegrityError, match="model/config/dataset"):
        run_variant_worker(
            completed_run / "unused-corpus",
            completed_run,
            variant="persona",
            git_commit=SOURCE,
            seed=24301,
            gpu_hours=0.1,
        )


def test_completed_adapter_cannot_be_relabelled_as_another_corpus(
    completed_run: Path,
) -> None:
    with pytest.raises(CampaignIntegrityError, match="model/config/dataset"):
        _verify(completed_run, dataset=replace(_dataset(), dataset_hash="d" * 64))


def test_completed_adapter_cannot_be_relabelled_as_another_native_model(
    completed_run: Path,
) -> None:
    with pytest.raises(CampaignIntegrityError, match="model/config/dataset"):
        _verify(completed_run, binding=resolve_model_binding("challenger"))


def test_completed_adapter_requires_original_training_seed(completed_run: Path) -> None:
    config = load_training_config("primary", mix=TrainingMix.OPERATIONAL)
    with pytest.raises(CampaignIntegrityError, match="model/config/dataset"):
        _verify(completed_run, config=replace(config, seed=config.seed + 1))


def test_completed_adapter_requires_exact_source_commit(completed_run: Path) -> None:
    with pytest.raises(CampaignIntegrityError, match="source revision differs"):
        _verify(completed_run, source_revision="a" * 40)
    with pytest.raises(CampaignIntegrityError, match="full immutable"):
        _verify(completed_run, source_revision="working-tree")


def test_run_manifest_dataset_must_agree_even_if_its_hash_is_updated(
    completed_run: Path,
) -> None:
    manifest = json.loads((completed_run / "run-manifest.json").read_text())
    manifest["payload"]["generator_config"]["dataset_identity"]["dataset_hash"] = (
        "e" * 64
    )
    _rewrite_manifest(completed_run, manifest)
    with pytest.raises(CampaignIntegrityError, match="manifest dataset_identity"):
        _verify(completed_run)


def test_completed_adapter_verifies_every_artifact_and_result_inventory(
    completed_run: Path,
) -> None:
    artifact = completed_run / "adapter/adapter_model.safetensors"
    artifact.write_bytes(b"changed")
    with pytest.raises(CampaignIntegrityError, match="artifact hash differs"):
        _verify(completed_run)


def test_completed_adapter_rejects_changed_manifest_before_reading_identity(
    completed_run: Path,
) -> None:
    path = completed_run / "run-manifest.json"
    path.write_text(path.read_text() + " ", encoding="utf-8")
    with pytest.raises(CampaignIntegrityError, match="manifest hash differs"):
        _verify(completed_run)


def test_completed_adapter_rejects_external_adapter_directory(
    completed_run: Path,
) -> None:
    result = json.loads((completed_run / "training-result.json").read_text())
    result["adapter_dir"] = str(completed_run.parent)
    _write(completed_run / "training-result.json", result)
    with pytest.raises(CampaignIntegrityError, match="adapter directory"):
        _verify(completed_run)


def test_completed_adapter_requires_result_run_identity(completed_run: Path) -> None:
    result = json.loads((completed_run / "training-result.json").read_text())
    result["run_id"] = "some-other-run"
    _write(completed_run / "training-result.json", result)
    with pytest.raises(CampaignIntegrityError, match="run identity differs"):
        _verify(completed_run)


def test_completed_adapter_refuses_an_unhashed_extra_file(completed_run: Path) -> None:
    (completed_run / "adapter" / "unexpected-weights.bin").write_bytes(b"not admitted")
    with pytest.raises(CampaignIntegrityError, match="undeclared"):
        _verify(completed_run)


@pytest.mark.parametrize("path", ["../outside", "..\\outside", "C:outside", "/outside"])
def test_completed_adapter_refuses_traversal_in_artifact_inventory(
    completed_run: Path, path: str
) -> None:
    result = json.loads((completed_run / "training-result.json").read_text())
    result["artifact_hashes"][path] = "f" * 64
    _write(completed_run / "training-result.json", result)
    manifest = json.loads((completed_run / "run-manifest.json").read_text())
    manifest["payload"]["artifact_hashes"] = result["artifact_hashes"]
    _rewrite_manifest(completed_run, manifest)
    with pytest.raises(CampaignIntegrityError, match="escapes"):
        _verify(completed_run)
