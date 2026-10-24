from __future__ import annotations

from pathlib import Path

import pytest

from techrotic_training_triumvirate.evaluation import frozen_evaluation_guard
from techrotic_training_triumvirate.training.pilot import (
    PILOT_MIXES,
    PilotPreparationError,
    authorize_pilot_budget,
    pilot_variant_matrix,
    run_pilot_smoke,
    validate_pilot_manifest,
)


def _manifest(*, frozen: int = 0) -> dict[str, object]:
    guard = frozen_evaluation_guard()
    shards: list[dict[str, object]] = [
        {
            "name": "train-00000.jsonl",
            "split": "train",
            "line_count": 3,
            "sha256": "a" * 64,
        }
    ]
    if frozen:
        shards.append(
            {
                "name": "frozen_eval-00000.jsonl",
                "split": "frozen_eval",
                "line_count": frozen,
                "sha256": "b" * 64,
            }
        )
    return {
        "manifest_version": 1,
        "config": {
            "frozen_evaluation_guard": {
                "benchmark_id": guard.benchmark_id,
                "benchmark_version": guard.benchmark_version,
                "benchmark_hash": guard.benchmark_hash,
            }
        },
        "tier_composition": {"T1": 1, "T2": 1, "T3": 1},
        "split_distribution": {"train": 3, "dev": 0, "frozen_eval": frozen},
        "shards": shards,
    }


def test_pilot_budget_uses_ttt_013_ceiling() -> None:
    admitted = authorize_pilot_budget(
        gpu_hours=24.0,
        external_compute_cost_gbp=75.0,
        opt_in=True,
    )
    assert admitted["gpu_hours"] == 24.0

    with pytest.raises(PilotPreparationError, match="TTT-013 limit"):
        authorize_pilot_budget(
            gpu_hours=24.01,
            external_compute_cost_gbp=1.0,
            opt_in=True,
        )
    with pytest.raises(PilotPreparationError, match="paid model/API"):
        authorize_pilot_budget(
            gpu_hours=1.0,
            external_compute_cost_gbp=1.0,
            paid_model_api_cost_gbp=0.01,
            opt_in=True,
        )


def test_pilot_manifest_requires_all_tiers_and_no_frozen_eval() -> None:
    validate_pilot_manifest(_manifest())  # type: ignore[arg-type]

    missing = _manifest()
    tiers = missing["tier_composition"]
    assert isinstance(tiers, dict)
    tiers["T3"] = 0
    with pytest.raises(PilotPreparationError, match="T3"):
        validate_pilot_manifest(missing)  # type: ignore[arg-type]

    with pytest.raises(PilotPreparationError, match="frozen evaluation"):
        validate_pilot_manifest(_manifest(frozen=1))  # type: ignore[arg-type]


def test_variant_matrix_has_four_comparable_primary_runs() -> None:
    variants = pilot_variant_matrix(
        model="primary",
        seed=24301,
        gpu_hours=24.0,
        external_compute_cost_gbp=40.0,
    )
    assert [item["variant_id"] for item in variants] == [
        mix.value for mix in PILOT_MIXES
    ]
    revisions = {
        item["model_binding"]["native_revision"]  # type: ignore[index]
        for item in variants
    }
    assert len(revisions) == 1
    assert sum(
        item["budget_cap"]["gpu_hours"]  # type: ignore[index,operator]
        for item in variants
    ) == 24.0


def test_four_way_smoke_is_not_reported_as_quality_evidence(tmp_path: Path) -> None:
    result = run_pilot_smoke(tmp_path, git_commit="test-head")
    assert result["quality_evidence"] is False
    assert result["substantive_campaign_executed"] is False
    variants = result["variants"]
    assert isinstance(variants, list)
    assert len(variants) == 4
    assert all(item["parity_passed"] is True for item in variants)
    assert (tmp_path / "smoke-comparison.json").is_file()
