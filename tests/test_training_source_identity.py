"""Source-bound native checkpoint identity checks without importing ML runtimes."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.schemas import canonical_json
from techrotic_training_triumvirate.training import (
    DatasetIdentity,
    TrainingMix,
    load_training_config,
    map_dataset,
    resolve_model_binding,
    smoke_source_examples,
)
from techrotic_training_triumvirate.training.campaign_integrity import (
    CampaignIntegrityError,
    expected_training_identity,
    verify_checkpoint_identity,
)
from techrotic_training_triumvirate.training.hf_peft import run_hf_peft_training
from techrotic_training_triumvirate.training.model import BudgetAuthorization

SOURCE = "11e70686b09a27cf7c784beaf8d7a46717b345a0"


def _identity(source: str | None = SOURCE) -> dict[str, object]:
    return dict(
        expected_training_identity(
            binding=resolve_model_binding("primary"),
            config=load_training_config("primary", mix=TrainingMix.OPERATIONAL),
            dataset=DatasetIdentity("a" * 64, "b" * 64, (), {}),
            source_revision=source,
        )
    )


def _verify(directory: Path, source: str = SOURCE) -> str:
    return verify_checkpoint_identity(
        directory,
        binding=resolve_model_binding("primary"),
        config=load_training_config("primary", mix=TrainingMix.OPERATIONAL),
        dataset=DatasetIdentity("a" * 64, "b" * 64, (), {}),
        source_revision=source,
    )


def _write(directory: Path, identity: object) -> None:
    (directory / "training-identity.json").write_text(
        canonical_json(identity) + "\n", encoding="utf-8"
    )


def test_checkpoint_v2_hash_binds_source_and_requires_exact_record(
    tmp_path: Path,
) -> None:
    identity = _identity()
    assert identity["schema_version"] == 2
    assert identity["source_revision"] == SOURCE
    assert _identity("a" * 40)["training_identity"] != identity["training_identity"]
    _write(tmp_path, identity)
    assert _verify(tmp_path) == identity["training_identity"]
    with pytest.raises(CampaignIntegrityError, match="source/model/config/dataset"):
        _verify(tmp_path, "a" * 40)
    identity["unexpected"] = "ignored fields are forbidden"
    _write(tmp_path, identity)
    with pytest.raises(CampaignIntegrityError, match="identity differs"):
        _verify(tmp_path)


@pytest.mark.parametrize("version", [1, 3, True, "2", None])
def test_ambiguous_or_malformed_checkpoint_versions_refuse(
    tmp_path: Path, version: object
) -> None:
    identity = _identity()
    identity["schema_version"] = version
    _write(tmp_path, identity)
    with pytest.raises(CampaignIntegrityError, match="identity v2"):
        _verify(tmp_path)


@pytest.mark.parametrize("identity", [[], "not an object", {"schema_version": 2}])
def test_malformed_checkpoint_identity_refuses(
    tmp_path: Path, identity: object
) -> None:
    _write(tmp_path, identity)
    with pytest.raises(CampaignIntegrityError):
        _verify(tmp_path)


@pytest.mark.parametrize("legacy", [True, False])
def test_hf_source_resume_refuses_before_any_heavy_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, legacy: bool
) -> None:
    _write(tmp_path, _identity(None if legacy else SOURCE))
    checkpoint = tmp_path / "checkpoints" / "checkpoint-1"
    checkpoint.mkdir(parents=True)
    (checkpoint / "trainer_state.json").write_text("{}", encoding="utf-8")

    real_import = importlib.import_module

    def no_heavy_import(name: str) -> object:
        if name in {"torch", "transformers", "peft"}:
            raise AssertionError(
                f"resume validation occurred after heavy import: {name}"
            )
        return real_import(name)

    monkeypatch.setattr(
        "techrotic_training_triumvirate.training.hf_peft.importlib.import_module",
        no_heavy_import,
    )
    config = load_training_config("primary", mix=TrainingMix.OPERATIONAL)
    with pytest.raises(CampaignIntegrityError):
        run_hf_peft_training(
            map_dataset(smoke_source_examples(), mix=config.mix),
            binding=resolve_model_binding("primary"),
            config=config,
            dataset=DatasetIdentity("a" * 64, "b" * 64, (), {}),
            budget=BudgetAuthorization(0.1, 0.0, 0.0),
            output_dir=tmp_path,
            git_commit="a" * 40,
            resume_from_checkpoint=str(checkpoint),
        )
    assert json.loads((tmp_path / "training-identity.json").read_text()) == _identity(
        None if legacy else SOURCE
    )
