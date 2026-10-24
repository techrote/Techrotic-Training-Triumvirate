"""Admission readback detects corruption and refuses inconsistent claims."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.admission import (
    AdmissionPackageError,
    evidence_reference,
    load_package,
    seal_package,
    verify_package,
    write_package,
)
from techrotic_training_triumvirate.cli import main
from techrotic_training_triumvirate.schemas import JsonObject, canonical_json


def _positive_package(root: Path, *, profile_version: int = 1) -> JsonObject:
    """Synthetic positive evidence tests validation, never model qualification."""
    from techrotic_training_triumvirate.evaluation import (
        PolicyIdentity,
        ScriptedCommanderBaseline,
        run_benchmark,
    )
    from techrotic_training_triumvirate.evaluation.closedloop import (
        ClosedLoopBaseline,
        run_closed_loop,
    )
    from techrotic_training_triumvirate.training import (
        DatasetIdentity,
        TrainingMix,
        load_training_config,
        resolve_model_binding,
    )
    from techrotic_training_triumvirate.training.campaign_integrity import (
        expected_training_identity,
    )
    from techrotic_training_triumvirate.training.export import build_run_manifest
    from techrotic_training_triumvirate.training.model import BudgetAuthorization

    # Entirely synthetic fixture records exercise readback contracts; these are
    # never published as actual training, hardware, human or model-quality evidence.
    binding = resolve_model_binding("primary")
    config = load_training_config(
        "primary",
        profile_version=profile_version,
        mix=TrainingMix.JOINT if profile_version == 1 else TrainingMix.JOINT_CORRECTIVE,
    )
    dataset = DatasetIdentity("d" * 64, "e" * 64, (("fixture.jsonl", "f" * 64),), {})
    parity = {
        "schema_version": 1,
        "passed": True,
        "cases": [
            {
                "example_id": "synthetic-fixture",
                "equal": True,
                "pre_export": "fixture",
                "post_export": "fixture",
            }
        ],
    }
    (root / "parity.json").write_text(canonical_json(parity), encoding="utf-8")
    manifest = build_run_manifest(
        phase="train-export",
        binding=binding,
        config=config,
        dataset=dataset,
        git_commit="a" * 40,
        backend=config.backend,
        artifact_hashes={
            "parity.json": evidence_reference(
                root, "parity.json", kind="export-parity"
            )["sha256"]
        },
        budget=BudgetAuthorization(0.01, 0.0, 0.0),
        command_line=("synthetic-test-fixture-only",),
        extra_runtime={
            "parity_passed": True,
            "training_identity": expected_training_identity(
                binding=binding,
                config=config,
                dataset=dataset,
                source_revision="a" * 40,
            )["training_identity"],
        },
    )

    class FrozenFixture(ScriptedCommanderBaseline):
        @property
        def identity(self) -> PolicyIdentity:
            return PolicyIdentity(
                "pilot-fixture", "recorded-policy-fixture", manifest.run_id
            )

    class ClosedFixture(ClosedLoopBaseline):
        @property
        def identity(self) -> PolicyIdentity:
            return PolicyIdentity(
                "pilot-fixture", "recorded-policy-fixture", manifest.run_id
            )

    package = _package(root)
    package["outcome"] = "ADMITTED"
    package["unavailable_artifacts"] = []
    candidate = package["candidates"][0]
    candidate["candidate_id"] = "pilot-fixture"
    candidate["base_model"] = "LiquidAI/LFM2.5-1.2B-Instruct"
    candidate["outcome"] = "ADMITTED"
    candidate["gates"] = {key: True for key in candidate["gates"]}
    evidence = {
        "frozen.json": (
            "frozen-evaluation",
            run_benchmark(FrozenFixture(), code_revision="a" * 40).to_dict(),
        ),
        "closed.json": (
            "closed-loop",
            run_closed_loop(
                ClosedFixture(),
                code_revision="a" * 40,
                candidate_metadata={
                    "variant": config.mix.value,
                    "substantive": True,
                    "base_checkpoint": binding.to_object(),
                    "dataset_hash": dataset.dataset_hash,
                    "training_run": manifest.run_id,
                },
                measure_runtime=False,
            ).to_dict(),
        ),
        "parity.json": ("export-parity", parity),
        "training-run.json": ("run-manifest", manifest.to_dict()),
        "human.json": (
            "human-ratings",
            {
                "schema": "ttt.human_ratings",
                "schema_version": 1,
                "candidate_id": "pilot-fixture",
                "ratings": [
                    {
                        "reviewer_id": "test-fixture-human",
                        "humour": 3,
                        "surprise": 4,
                        "distinctiveness": 5,
                    }
                ],
            },
        ),
        "runtime.json": (
            "runtime-measurements",
            {
                "schema": "ttt.runtime_measurements",
                "schema_version": 1,
                "candidate_id": "pilot-fixture",
                "model_role": "primary",
                "quantization": "Q4_K_M",
                "host": "synthetic test fixture",
                "artifact_sha256": "b" * 64,
                "context_tokens": 2048,
                "artifact_size_bytes": 731_000_000,
                "peak_resident_memory_bytes": 2_000_000_000,
                "ttft_seconds": 1.0,
                "decode_tokens_per_second": 15.0,
            },
        ),
    }
    for name, (kind, value) in evidence.items():
        (root / name).write_text(canonical_json(value), encoding="utf-8")
        package["evidence"].append(evidence_reference(root, name, kind=kind))
        candidate["evidence_refs"].append(name)
    return package


def test_registered_repair_profile_has_the_same_positive_evidence_gates(
    tmp_path: Path,
) -> None:
    package = _positive_package(tmp_path, profile_version=2)
    path = tmp_path / "repair-package.json"
    write_package(path, package, evidence_root=tmp_path)
    assert verify_package(path, evidence_root=tmp_path)["outcome"] == "ADMITTED"
    run = load_package(tmp_path / "training-run.json")
    run["payload"]["generator_config"]["training_config"]["epochs"] = 2
    _replace_evidence(tmp_path, package, "training-run.json", run)
    with pytest.raises(AdmissionPackageError, match="configuration mismatch"):
        write_package(path, package, evidence_root=tmp_path)


def _replace_evidence(
    root: Path, package: JsonObject, name: str, value: object
) -> None:
    (root / name).write_text(canonical_json(value), encoding="utf-8")
    for index, reference in enumerate(package["evidence"]):
        if reference["path"] == name:
            package["evidence"][index] = evidence_reference(
                root, name, kind=reference["kind"]
            )


def _package(root: Path) -> JsonObject:
    references = []
    for name in ("report.md", "data-card.md", "model-card.md", "run.json"):
        (root / name).write_text(f"evidence for {name}\n", encoding="utf-8")
        references.append(evidence_reference(root, name, kind="provenance"))
    return {
        "schema": "ttt.final_admission",
        "schema_version": 1,
        "programme_id": "TTT-016",
        "code_revision": "a" * 40,
        "outcome": "NOT ADMITTED",
        "rationale": ["Candidate failed mechanical qualification."],
        "evidence": references,
        "candidates": [
            {
                "candidate_id": "pilot-joint-24301",
                "base_model": "admitted-primary@immutable-revision",
                "outcome": "NOT ADMITTED",
                "model_card": "model-card.md",
                "evidence_refs": ["run.json"],
                "gates": {
                    "frozen_evaluation": False,
                    "closed_loop": False,
                    "hidden_information": False,
                    "export_parity": True,
                    "runtime": False,
                    "provenance": True,
                    "human_review": False,
                },
                "constraints": [],
            }
        ],
        "data_card": "data-card.md",
        "report": "report.md",
        "limitations": ["Human ratings unavailable."],
        "unavailable_artifacts": ["Local-only adapter; see model card."],
    }


def test_negative_package_readback_and_altered_fixture(tmp_path: Path) -> None:
    path = tmp_path / "admission.json"
    result = write_package(path, _package(tmp_path), evidence_root=tmp_path)
    assert result["verified"] is True
    assert result["verified_files"] == 4
    assert result["candidate_count"] == 1
    (tmp_path / "run.json").write_text("ALTERED", encoding="utf-8")
    with pytest.raises(AdmissionPackageError, match="evidence hash mismatch"):
        verify_package(path, evidence_root=tmp_path)


def test_package_decision_tampering(tmp_path: Path) -> None:
    path = tmp_path / "admission.json"
    write_package(path, _package(tmp_path), evidence_root=tmp_path)
    raw = load_package(path)
    raw["outcome"] = "ADMITTED"
    path.write_text(canonical_json(raw), encoding="utf-8")
    with pytest.raises(AdmissionPackageError, match="content hash mismatch"):
        verify_package(path, evidence_root=tmp_path)


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/secrets", "a\\b"])
def test_evidence_path_escape_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(AdmissionPackageError, match="unsafe"):
        evidence_reference(tmp_path, name, kind="provenance")


def test_missing_evidence_and_unbound_card(tmp_path: Path) -> None:
    path = tmp_path / "admission.json"
    package = _package(tmp_path)
    package["data_card"] = "unhashed.md"
    with pytest.raises(AdmissionPackageError, match="hashed evidence"):
        write_package(path, package, evidence_root=tmp_path)
    package["data_card"] = "data-card.md"
    (tmp_path / "run.json").unlink()
    with pytest.raises(AdmissionPackageError, match="missing"):
        write_package(path, package, evidence_root=tmp_path)


@pytest.mark.parametrize("outcome", ["ADMITTED", "CONDITIONALLY ADMITTED"])
def test_positive_admission_cannot_waive_safety(tmp_path: Path, outcome: str) -> None:
    package = _package(tmp_path)
    candidates = package["candidates"]
    assert isinstance(candidates, list) and isinstance(candidates[0], dict)
    candidates[0]["outcome"] = outcome
    package["outcome"] = outcome
    with pytest.raises(AdmissionPackageError, match="unmet gates|safety gates"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_duplicate_json_keys_and_nonfinite_numbers_refused(tmp_path: Path) -> None:
    path = tmp_path / "admission.json"
    for raw in (
        '{"outcome": "ADMITTED", "outcome": "NOT ADMITTED"}',
        '{"x": NaN}',
        '{"x": 1e999}',
    ):
        path.write_text(raw, encoding="utf-8")
        with pytest.raises(AdmissionPackageError):
            load_package(path)


def test_unknown_version_and_unknown_fields_refused(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["schema_version"] = True
    with pytest.raises(AdmissionPackageError, match="unsupported"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)
    package["schema_version"] = 1
    package["extra"] = "ignored"
    with pytest.raises(AdmissionPackageError, match="fields"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_duplicate_candidate_refused(tmp_path: Path) -> None:
    package = _package(tmp_path)
    candidates = package["candidates"]
    assert isinstance(candidates, list)
    candidates.append(candidates[0])
    with pytest.raises(AdmissionPackageError, match="duplicate candidate"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_positive_programme_requires_a_candidate(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["candidates"] = []
    package["outcome"] = "ADMITTED"
    with pytest.raises(AdmissionPackageError, match="matching candidate"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_package_seal_is_canonical(tmp_path: Path) -> None:
    package = _package(tmp_path)
    assert seal_package(package) == seal_package(dict(reversed(list(package.items()))))
    assert (
        json.loads(canonical_json(seal_package(package)))["outcome"] == "NOT ADMITTED"
    )


def test_readback_cli_fails_after_evidence_corruption(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "admission.json"
    write_package(path, _package(tmp_path), evidence_root=tmp_path)
    argv = ["admission-verify", "--package", str(path), "--root", str(tmp_path)]
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True
    (tmp_path / "report.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(SystemExit) as failure:
        main(argv)
    assert failure.value.code == 1
    assert "hash mismatch" in capsys.readouterr().err


def test_positive_package_requires_matching_measured_evidence(tmp_path: Path) -> None:
    package = _positive_package(tmp_path)
    result = write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)
    assert result["outcome"] == "ADMITTED"


@pytest.mark.parametrize(
    "name,change,match",
    [
        ("parity.json", "failed-parity", "failed export parity"),
        ("human.json", "empty-ratings", "supplied ratings"),
        ("human.json", "null-score", "supplied integers"),
        ("runtime.json", "slow-runtime", "runtime targets"),
        ("runtime.json", "native-runtime", "Q4/model role"),
        ("runtime.json", "wrong-candidate", "another candidate"),
        ("runtime.json", "wrong-role", "model role contradicts"),
        ("frozen.json", "wrong-policy", "candidate identity"),
        ("frozen.json", "omit-case", "full-suite case coverage"),
        ("frozen.json", "inflate-score", "contradicts case metrics"),
        ("frozen.json", "no-commands", "actual frozen command execution"),
    ],
)
def test_hash_valid_positive_claim_cannot_override_failed_or_unrelated_evidence(
    tmp_path: Path,
    name: str,
    change: str,
    match: str,
) -> None:
    package = _positive_package(tmp_path)
    value = json.loads((tmp_path / name).read_text(encoding="utf-8"))
    if change == "failed-parity":
        value.update(passed=False, cases=[{"equal": False}])
    elif change == "empty-ratings":
        value["ratings"] = []
    elif change == "null-score":
        value["ratings"][0]["humour"] = None
    elif change == "slow-runtime":
        value["decode_tokens_per_second"] = 1.0
    elif change == "native-runtime":
        value["quantization"] = "none"
    elif change == "wrong-candidate":
        value["candidate_id"] = "other-model"
    elif change == "wrong-role":
        value["model_role"] = "challenger"
    elif change == "wrong-policy":
        value["policy"]["policy_id"] = "other-model"
    elif change == "omit-case":
        value["cases"].pop()
    elif change == "inflate-score":
        value["operational"]["mechanical"]["score"] = 1.0
    elif change == "no-commands":
        for case in value["cases"]:
            case.update(command_count=0, accepted_count=0, rejected_count=0)
    _replace_evidence(tmp_path, package, name, value)
    with pytest.raises(AdmissionPackageError, match=match):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_conditional_admission_may_defer_only_runtime_and_human_review(
    tmp_path: Path,
) -> None:
    package = _positive_package(tmp_path)
    package["outcome"] = "CONDITIONALLY ADMITTED"
    candidate = package["candidates"][0]
    candidate["outcome"] = "CONDITIONALLY ADMITTED"
    candidate["constraints"] = ["Research-only until Q4 and human qualification."]
    candidate["gates"]["runtime"] = False
    candidate["gates"]["human_review"] = False
    candidate["evidence_refs"] = [
        name
        for name in candidate["evidence_refs"]
        if name not in {"human.json", "runtime.json"}
    ]
    package["evidence"] = [
        reference
        for reference in package["evidence"]
        if reference["path"] not in {"human.json", "runtime.json"}
    ]
    result = write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)
    assert result["outcome"] == "CONDITIONALLY ADMITTED"


@pytest.mark.parametrize("outcome", ["ADMITTED", "CONDITIONALLY ADMITTED"])
@pytest.mark.parametrize(
    "base_model",
    [
        "Unadmitted/Completely-Different-Model@main",
        "LiquidAI/LFM2.5-1.2B-Instruct@main",
        "kandivault/sprocket-500m",
    ],
)
def test_every_positive_outcome_requires_admitted_immutable_student(
    tmp_path: Path,
    outcome: str,
    base_model: str,
) -> None:
    package = _positive_package(tmp_path)
    package["outcome"] = outcome
    candidate = package["candidates"][0]
    candidate.update(outcome=outcome, base_model=base_model)
    if outcome == "CONDITIONALLY ADMITTED":
        candidate["constraints"] = ["Awaiting runtime and human qualification."]
        candidate["gates"].update(runtime=False, human_review=False)
    with pytest.raises(AdmissionPackageError, match="admitted immutable student"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


@pytest.mark.parametrize(
    "case",
    [
        {"equal": True},
        {"equal": True, "pre_export": "before", "post_export": "after"},
        {"equal": True, "pre_export_sha256": "a" * 64, "exported_sha256": "b" * 64},
        {
            "equal": True,
            "pre_export": "matching",
            "post_export": "matching",
            "pre_export_sha256": "a" * 64,
            "exported_sha256": "a" * 64,
        },
    ],
)
def test_passing_parity_requires_consistent_comparable_values(
    tmp_path: Path,
    case: dict[str, object],
) -> None:
    package = _positive_package(tmp_path)
    _replace_evidence(
        tmp_path, package, "parity.json", {"passed": True, "cases": [case]}
    )
    with pytest.raises(AdmissionPackageError, match="parity"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_positive_provenance_cannot_be_replaced_by_plain_kind_label(
    tmp_path: Path,
) -> None:
    package = _positive_package(tmp_path)
    for reference in package["evidence"]:
        if reference["path"] == "training-run.json":
            reference["kind"] = "provenance"
    with pytest.raises(AdmissionPackageError, match="lacks verifiable evidence"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


@pytest.mark.parametrize(
    "change,match",
    [
        ("source", "source/model binding"),
        ("model", "source/model binding"),
        ("config", "configuration mismatch"),
        ("dataset", "dataset contradicts"),
        ("run", "matching canonical provenance"),
        ("training-identity", "training identity mismatch"),
        ("parity-hash", "parity hash is not bound"),
    ],
)
def test_positive_provenance_must_match_actual_candidate_identity(
    tmp_path: Path,
    change: str,
    match: str,
) -> None:
    package = _positive_package(tmp_path)
    value = json.loads((tmp_path / "training-run.json").read_text())
    payload = value["payload"]
    if change == "source":
        payload["git_commit"] = "c" * 40
    elif change == "model":
        payload["generator_config"]["model_binding"]["native_revision"] = "main"
    elif change == "config":
        payload["generator_config"]["training_config"]["mix"] = "operational"
    elif change == "dataset":
        payload["generator_config"]["dataset_identity"]["dataset_hash"] = "c" * 64
    elif change == "run":
        payload["run_id"] = "another-run"
    elif change == "training-identity":
        payload["runtime"]["training_identity"] = "0" * 64
    elif change == "parity-hash":
        payload["artifact_hashes"]["parity.json"] = "0" * 64
    _replace_evidence(tmp_path, package, "training-run.json", value)
    with pytest.raises(AdmissionPackageError, match=match):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_positive_closed_loop_metadata_must_identify_same_base(tmp_path: Path) -> None:
    from techrotic_training_triumvirate.evaluation.closedloop import ClosedLoopReport

    package = _positive_package(tmp_path)
    value = json.loads((tmp_path / "closed.json").read_text())
    value["evidence"]["candidate_metadata"]["base_checkpoint"]["native_revision"] = (
        "main"
    )
    resealed = ClosedLoopReport(value["evidence"], value["runtime"]).to_dict()
    _replace_evidence(tmp_path, package, "closed.json", resealed)
    with pytest.raises(AdmissionPackageError, match="base binding contradicts"):
        write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)


def test_negative_package_preserves_failed_and_legacy_parity(tmp_path: Path) -> None:
    package = _package(tmp_path)
    failed = {"schema_version": 1, "passed": False, "cases": [{"equal": False}]}
    (tmp_path / "failed-parity.json").write_text(
        canonical_json(failed), encoding="utf-8"
    )
    package["evidence"].append(
        evidence_reference(tmp_path, "failed-parity.json", kind="export-parity")
    )
    package["candidates"][0]["evidence_refs"].append("failed-parity.json")
    package["candidates"][0]["gates"]["export_parity"] = False
    legacy = {"passed": True, "cases": [{"equal": True}]}
    (tmp_path / "legacy-parity.json").write_text(
        canonical_json(legacy), encoding="utf-8"
    )
    package["evidence"].append(
        evidence_reference(tmp_path, "legacy-parity.json", kind="export-parity")
    )
    package["candidates"][0]["evidence_refs"].append("legacy-parity.json")
    result = write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)
    assert result["verified"] is True
    assert result["outcome"] == "NOT ADMITTED"


def test_positive_tiny_sha_parity_comparison_is_supported(tmp_path: Path) -> None:
    package = _positive_package(tmp_path)
    parity = {
        "passed": True,
        "cases": [
            {
                "equal": True,
                "pre_export_sha256": "b" * 64,
                "exported_sha256": "b" * 64,
            }
        ],
    }
    _replace_evidence(tmp_path, package, "parity.json", parity)
    manifest = json.loads((tmp_path / "training-run.json").read_text())
    manifest["payload"]["artifact_hashes"]["parity.json"] = evidence_reference(
        tmp_path, "parity.json", kind="export-parity"
    )["sha256"]
    _replace_evidence(tmp_path, package, "training-run.json", manifest)
    result = write_package(tmp_path / "admission.json", package, evidence_root=tmp_path)
    assert result["outcome"] == "ADMITTED"
