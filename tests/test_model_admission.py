from __future__ import annotations

import copy

import pytest

from techrotic_training_triumvirate.model_admission import (
    ModelAdmissionError,
    load_model_cast_v1,
    model_cast_content_hash,
    selected_model_keys,
    validate_model_cast_v1,
)


def test_committed_model_cast_is_selected_and_valid() -> None:
    data = load_model_cast_v1()
    validate_model_cast_v1(data)

    assert data["decision_status"] == "SELECTED"
    assert data["roles"]["primary_compact_student"] == "lfm2.5-1.2b-instruct"
    assert selected_model_keys() == (
        "lfm2.5-1.2b-instruct",
        "qwen3.5-4b",
        "sprocket-500m",
    )


def test_model_cast_hash_is_stable() -> None:
    data = load_model_cast_v1()
    assert model_cast_content_hash(data) == model_cast_content_hash(copy.deepcopy(data))


def test_mutable_ref_cannot_be_sole_identity() -> None:
    data = load_model_cast_v1()
    lfm = data["models"]["lfm2.5-1.2b-instruct"]["native"]
    lfm.pop("artifact_sha256")
    lfm["artifact_commit"] = "main"

    with pytest.raises(ModelAdmissionError, match="mutable ref"):
        validate_model_cast_v1(data)


def test_missing_license_disposition_is_rejected() -> None:
    data = load_model_cast_v1()
    data["models"]["qwen3.5-4b"]["license"]["generated_output_training_use"] = ""

    with pytest.raises(ModelAdmissionError, match="generated_output_training_use"):
        validate_model_cast_v1(data)
