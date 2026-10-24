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


def _positive_package(root: Path) -> JsonObject:
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

    class FrozenFixture(ScriptedCommanderBaseline):
        @property
        def identity(self) -> PolicyIdentity:
            return PolicyIdentity("pilot-fixture", "recorded-policy-fixture", "v1")

    class ClosedFixture(ClosedLoopBaseline):
        @property
        def identity(self) -> PolicyIdentity:
            return PolicyIdentity("pilot-fixture", "recorded-policy-fixture", "v1")

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
                candidate_metadata={"variant": "joint", "substantive": True},
                measure_runtime=False,
            ).to_dict(),
        ),
        "parity.json": ("export-parity", {"passed": True, "cases": [{"equal": True}]}),
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
