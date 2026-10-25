"""Qualification reporting cannot borrow results or substitute another binary."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

from techrotic_training_triumvirate.admission import (
    AdmissionPackageError,
    evidence_reference,
    load_package,
    verify_package,
)
from techrotic_training_triumvirate.evaluation import (
    PolicyIdentity,
    ScriptedCommanderBaseline,
    run_benchmark,
)
from techrotic_training_triumvirate.evaluation.closedloop import (
    ClosedLoopBaseline,
    run_closed_loop,
)
from techrotic_training_triumvirate.training.export import sha256_file


def builder(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "commander_evidence_test", scripts / "build_commander_evidence.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_graph_setting_cannot_be_changed_by_unrecorded_parent_env(
    monkeypatch,
) -> None:
    builder(monkeypatch)
    from evaluate_q4_commander import TITAN, configure_cuda_graphs

    parent = {"CUDA_VISIBLE_DEVICES": TITAN, "GGML_CUDA_DISABLE_GRAPHS": "0"}
    enabled = configure_cuda_graphs(parent, disabled=False)
    # llama.cpp tests presence, so even an inherited value of "0" disables it.
    assert "GGML_CUDA_DISABLE_GRAPHS" not in enabled
    disabled = configure_cuda_graphs(parent, disabled=True)
    assert disabled["GGML_CUDA_DISABLE_GRAPHS"] == "1"
    assert disabled["CUDA_VISIBLE_DEVICES"] == TITAN
    assert parent["GGML_CUDA_DISABLE_GRAPHS"] == "0"


class FrozenFixture(ScriptedCommanderBaseline):
    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity("synthetic-fixture", "test-only", "fixture-run")


class LongFixture(ClosedLoopBaseline):
    @property
    def identity(self) -> PolicyIdentity:
        return FrozenFixture().identity


def test_qualification_metrics_reject_failed_recovery_and_borrowed_identity(
    monkeypatch,
) -> None:
    module = builder(monkeypatch)
    frozen = run_benchmark(FrozenFixture(), code_revision="fixture").to_dict()
    closed = run_closed_loop(
        LongFixture(), code_revision="fixture", measure_runtime=False
    ).to_dict()
    assert module.metrics(frozen, closed)["passed"] is True
    failed = copy.deepcopy(frozen)
    failed["operational"]["mechanical"]["rejection_recovery_rate"] = 0.5
    assert module.metrics(failed, closed)["passed"] is False
    empty = copy.deepcopy(frozen)
    for case in empty["cases"]:
        case["command_count"] = 0
    assert module.metrics(empty, closed)["passed"] is False
    leaked = copy.deepcopy(frozen)
    leaked["operational"]["hidden_information"]["hidden_fact_use_count"] = 1
    assert module.metrics(leaked, closed)["passed"] is False
    other = copy.deepcopy(frozen)
    other["policy"]["revision"] = "different-checkpoint"
    with pytest.raises(ValueError, match="identities differ"):
        module.metrics(other, closed)


def test_runtime_measurements_require_the_actual_same_binary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = builder(monkeypatch)
    binary = tmp_path / "synthetic.gguf"
    binary.write_bytes(b"small test fixture, not model weights")
    runtime = {
        "artifact_sha256": sha256_file(binary),
        "artifact_size_bytes": binary.stat().st_size,
    }
    module.verify_runtime_binary(runtime, binary)
    binary.write_bytes(b"X" * runtime["artifact_size_bytes"])
    with pytest.raises(ValueError, match="actual Q4 binary"):
        module.verify_runtime_binary(runtime, binary)


def test_input_references_refuse_paths_outside_the_root(tmp_path: Path, monkeypatch):
    module = builder(monkeypatch)
    root = tmp_path / "root"
    root.mkdir()
    other = tmp_path / "outside.json"
    other.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="escaped input"):
        module.relative(root, other)


def test_allocation_refuses_unknown_lifetime_wrong_gpu_and_erased_charges(monkeypatch):
    module = builder(monkeypatch)
    ledger = {
        "charged_gpu_hours": 0.25,
        "attempts": [
            {
                "status": 0,
                "gpu_uuid": module.TITAN,
                "hours": 1,
                "actual_gpu_hours": 0.25,
            }
        ],
    }
    module.verify_allocation(ledger)
    unknown = copy.deepcopy(ledger)
    unknown["attempts"][0]["status"] = "reserved"
    with pytest.raises(ValueError, match="unresolved"):
        module.verify_allocation(unknown)
    wrong = copy.deepcopy(ledger)
    wrong["attempts"][0]["gpu_uuid"] = "GPU-not-the-admitted-TITAN"
    with pytest.raises(ValueError, match="another physical GPU"):
        module.verify_allocation(wrong)
    missing = copy.deepcopy(ledger)
    del missing["attempts"][0]["gpu_uuid"]
    with pytest.raises(ValueError, match="another physical GPU"):
        module.verify_allocation(missing)
    erased = copy.deepcopy(ledger)
    erased["charged_gpu_hours"] = 0
    with pytest.raises(ValueError, match="differs from attempt charges"):
        module.verify_allocation(erased)


def fixture_renderer(*, missing_rating: bool):
    # The original verifier's synthetic fixture exercises publication only.
    # These scripted/test ratings never constitute real qualification evidence.
    from test_admission import _positive_package, _replace_evidence

    def render(stage, destination):
        package = _positive_package(destination, profile_version=2)
        if missing_rating:
            human = load_package(destination / "human.json")
            human["ratings"][0]["humour"] = None
            _replace_evidence(destination, package, "human.json", human)
        prefix = destination.relative_to(stage).as_posix() + "/"
        for reference in package["evidence"]:
            reference["path"] = prefix + reference["path"]
        for candidate in package["candidates"]:
            candidate["model_card"] = prefix + candidate["model_card"]
            candidate["evidence_refs"] = [
                prefix + p for p in candidate["evidence_refs"]
            ]
            candidate["evidence_refs"].append("external.bin")
        package["data_card"] = prefix + package["data_card"]
        package["report"] = prefix + package["report"]
        package["evidence"].append(
            evidence_reference(stage, "external.bin", kind="fixture-binary")
        )
        return package

    return render


def test_failed_human_readback_publishes_no_admission_result(
    tmp_path: Path, monkeypatch
):
    module = builder(monkeypatch)
    binary = tmp_path / "external.bin"
    binary.write_bytes(b"unpublished synthetic fixture")
    output = tmp_path / "final"
    with pytest.raises(AdmissionPackageError):
        module.publish_staged(
            tmp_path,
            output,
            {"external.bin": "fixture-binary"},
            fixture_renderer(missing_rating=True),
        )
    assert not output.exists()
    assert binary.read_bytes() == b"unpublished synthetic fixture"
    assert list((tmp_path / "artifacts").iterdir()) == []


def test_published_readback_still_requires_bound_local_binary(
    tmp_path: Path, monkeypatch
):
    module = builder(monkeypatch)
    binary = tmp_path / "external.bin"
    binary.write_bytes(b"unpublished synthetic fixture")
    output = tmp_path / "final"
    result = module.publish_staged(
        tmp_path,
        output,
        {"external.bin": "fixture-binary"},
        fixture_renderer(missing_rating=False),
    )
    assert result["outcome"] == "ADMITTED"  # Synthetic verifier fixture only.
    assert list((tmp_path / "artifacts").iterdir()) == []
    binary.unlink()
    with pytest.raises(AdmissionPackageError, match="missing"):
        verify_package(output / "admission-package.json", evidence_root=tmp_path)
