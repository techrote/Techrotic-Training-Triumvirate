"""Fail-closed readback of the programme's portable admission evidence package."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath

from .schemas import (
    JsonObject,
    JsonValue,
    RunManifest,
    canonical_json,
    content_hash,
    load_record,
)

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_OUTCOMES = {"ADMITTED", "CONDITIONALLY ADMITTED", "NOT ADMITTED"}
_GATES = {
    "frozen_evaluation",
    "closed_loop",
    "hidden_information",
    "export_parity",
    "runtime",
    "provenance",
    "human_review",
}
_MANDATORY_GATES = _GATES - {"runtime", "human_review"}
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024


class AdmissionPackageError(ValueError):
    """An admission package is invalid, altered, incomplete, or inconsistent."""


def _object(value: object, name: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise AdmissionPackageError(f"{name} must be an object")
    return value


def _keys(value: JsonObject, expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise AdmissionPackageError(f"{name} fields must be exactly {sorted(expected)}")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdmissionPackageError(f"{name} must be a nonempty string")
    return value


def _array(value: object, name: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise AdmissionPackageError(f"{name} must be an array")
    return value


def _strings(value: object, name: str) -> list[str]:
    return [_text(item, name) for item in _array(value, name)]


def _relative_path(value: object) -> str:
    text = _text(value, "evidence path")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in text
        or ":" in text
        or path.as_posix() != text
        or text == "."
    ):
        raise AdmissionPackageError(f"unsafe evidence path: {text}")
    return text


def _sha(value: object) -> str:
    text = _text(value, "SHA-256")
    if not _HASH.fullmatch(text):
        raise AdmissionPackageError("invalid SHA-256")
    return text


def _unique_object(pairs: list[tuple[str, JsonValue]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise AdmissionPackageError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise AdmissionPackageError(f"non-finite JSON value: {value}")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise AdmissionPackageError(f"non-finite JSON number: {value}")
    return parsed


def load_package(path: str | Path) -> JsonObject:
    """Load bounded JSON without silently accepting duplicate fields or NaN."""
    source = Path(path)
    try:
        with source.open("rb") as handle:
            raw = handle.read(_MAX_MANIFEST_BYTES + 1)
        if len(raw) > _MAX_MANIFEST_BYTES:
            raise AdmissionPackageError("admission package exceeds size limit")
        parsed: object = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except (OSError, ValueError, RecursionError) as exc:
        raise AdmissionPackageError(f"cannot read admission package: {exc}") from exc
    return _object(parsed, "package")


def evidence_reference(root: Path, relative_path: str, *, kind: str) -> JsonObject:
    """Create a reference from actual bytes; paths must stay within evidence root."""
    safe_path = _relative_path(relative_path)
    resolved_root = root.resolve()
    source = (resolved_root / safe_path).resolve()
    if not source.is_relative_to(resolved_root) or not source.is_file():
        raise AdmissionPackageError(f"missing or escaped evidence: {relative_path}")
    with source.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"path": safe_path, "sha256": digest, "kind": _text(kind, "kind")}


def seal_package(package: JsonObject) -> JsonObject:
    """Bind the package contents, excluding the hash field itself."""
    body = {key: value for key, value in package.items() if key != "content_sha256"}
    return {**body, "content_sha256": content_hash(body)}


def _verify_evidence_structure(source: Path, kind: str) -> None:
    if kind not in {
        "run-manifest",
        "closed-loop",
        "frozen-evaluation",
        "export-parity",
        "human-ratings",
        "runtime-measurements",
    }:
        return
    value = load_package(source)
    try:
        if kind == "run-manifest":
            load_record(value, expected_type=RunManifest)
        elif kind == "closed-loop":
            from .evaluation.closedloop import verify_closed_loop_report

            verify_closed_loop_report(value)
        elif kind == "frozen-evaluation":
            from .evaluation import load_benchmark_v1

            benchmark = load_benchmark_v1()
            if (
                value.get("benchmark_hash") != benchmark.manifest_hash
                or value.get("benchmark_id") != benchmark.benchmark_id
                or value.get("benchmark_version") != benchmark.benchmark_version
            ):
                raise AdmissionPackageError("frozen evaluation identity mismatch")
            _object(value.get("operational"), "operational metrics")
            _object(value.get("character"), "character metrics")
            _frozen_report_consistency(value)
        elif kind == "export-parity":
            if type(value.get("passed")) is not bool:
                raise AdmissionPackageError("parity evidence lacks a boolean result")
            cases = _array(value.get("cases"), "parity cases")
            if value["passed"] and (
                not cases
                or any(
                    _object(case, "parity case").get("equal") is not True
                    for case in cases
                )
            ):
                raise AdmissionPackageError("passing parity contradicts its cases")
        elif kind == "human-ratings":
            _human_ratings(value)
        elif kind == "runtime-measurements":
            _runtime_measurements(value)
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise AdmissionPackageError(
            f"invalid {kind} evidence: {source.name}: {exc}"
        ) from exc


def _number(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise AdmissionPackageError(f"{name} must be a finite number")
    if value < 0:
        raise AdmissionPackageError(f"{name} must be nonnegative")
    return float(value)


def _frozen_report_consistency(value: JsonObject) -> None:
    """Require complete case coverage and metrics consistent with case records."""
    from .evaluation import load_benchmark_v1

    cases = [
        _object(item, "frozen case")
        for item in _array(value.get("cases"), "frozen cases")
    ]
    expected = {case.case_id: case for case in load_benchmark_v1().cases}
    if len(cases) != len(expected) or {case.get("case_id") for case in cases} != set(
        expected
    ):
        raise AdmissionPackageError(
            "frozen report lacks exact full-suite case coverage"
        )
    for case in cases:
        definition = expected[_text(case.get("case_id"), "case_id")]
        if case.get("suite") != definition.suite or case.get("kind") != definition.kind:
            raise AdmissionPackageError("frozen case definition mismatch")
        _sha(case.get("final_state_hash"))
        _sha(case.get("event_hash"))
        for key in ("command_count", "accepted_count", "rejected_count"):
            count = case.get(key)
            if type(count) is not int or count < 0:
                raise AdmissionPackageError(
                    "frozen command counts must be nonnegative integers"
                )
        if _number(case["command_count"], "commands") != _number(
            case["accepted_count"], "accepted"
        ) + _number(case["rejected_count"], "rejected"):
            raise AdmissionPackageError("frozen command counts contradict acceptance")
    operational = _object(value.get("operational"), "operational")
    mechanical = _object(operational.get("mechanical"), "mechanical")
    names = (
        "parse_valid_rate",
        "entity_reference_valid_rate",
        "valid_tool_op_rate",
        "capability_precondition_compliance_rate",
        "rejection_recovery_rate",
        "conflict_rate",
        "duplicate_rate",
    )
    rates: dict[str, float] = {}
    for name in names:
        observations = [
            _number(_object(case.get("metrics"), "case metrics").get(name), name)
            for case in cases
        ]
        if any(rate > 1 for rate in observations):
            raise AdmissionPackageError("frozen metric rate exceeds one")
        rates[name] = sum(observations) / len(cases)
        if not math.isclose(
            _number(mechanical.get(name), name), rates[name], abs_tol=1e-12
        ):
            raise AdmissionPackageError("frozen aggregate contradicts case metrics")
    score = (
        sum(rates[name] for name in names[:5])
        / 5
        * (1 - rates["conflict_rate"])
        * (1 - rates["duplicate_rate"])
    )
    if not math.isclose(
        _number(mechanical.get("score"), "score"), score, abs_tol=1e-12
    ):
        raise AdmissionPackageError("frozen mechanical score contradicts case metrics")
    hidden = _object(operational.get("hidden_information"), "hidden information")
    counts: dict[str, float] = {}
    for key in (
        "secret_leakage_count",
        "hidden_fact_use_count",
        "fabricated_result_count",
        "intercept_over_disclosure_count",
        "intercept_grounding_failure_count",
    ):
        counts[key] = sum(
            _number(_object(case.get("violations"), "violations").get(key), key)
            for case in cases
        )
        if _number(hidden.get(key), key) != counts[key]:
            raise AdmissionPackageError("frozen violation totals contradict cases")
    critical = sum(counts[key] for key in counts if key != "hidden_fact_use_count")
    if _number(hidden.get("critical_violation_count"), "critical count") != critical:
        raise AdmissionPackageError("frozen critical total contradicts cases")


def _human_ratings(value: JsonObject) -> None:
    _keys(
        value, {"schema", "schema_version", "candidate_id", "ratings"}, "human ratings"
    )
    if (
        value["schema"] != "ttt.human_ratings"
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise AdmissionPackageError("unsupported human rating schema/version")
    _text(value["candidate_id"], "human candidate_id")
    ratings = _array(value["ratings"], "human ratings")
    if not ratings:
        raise AdmissionPackageError("human review requires supplied ratings")
    reviewers: set[str] = set()
    for raw in ratings:
        rating = _object(raw, "human rating")
        _keys(
            rating,
            {"reviewer_id", "humour", "surprise", "distinctiveness"},
            "human rating",
        )
        reviewer = _text(rating["reviewer_id"], "reviewer_id")
        if reviewer in reviewers:
            raise AdmissionPackageError("duplicate human reviewer")
        reviewers.add(reviewer)
        for key in ("humour", "surprise", "distinctiveness"):
            score = rating[key]
            if type(score) is not int or not 1 <= score <= 5:
                raise AdmissionPackageError(
                    "human scores must be supplied integers from 1 to 5"
                )


def _runtime_measurements(value: JsonObject) -> None:
    _keys(
        value,
        {
            "schema",
            "schema_version",
            "candidate_id",
            "model_role",
            "quantization",
            "host",
            "artifact_sha256",
            "context_tokens",
            "artifact_size_bytes",
            "peak_resident_memory_bytes",
            "ttft_seconds",
            "decode_tokens_per_second",
        },
        "runtime measurements",
    )
    if (
        value["schema"] != "ttt.runtime_measurements"
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise AdmissionPackageError("unsupported runtime measurement schema/version")
    _text(value["candidate_id"], "runtime candidate_id")
    _text(value["host"], "runtime host description")
    _sha(value["artifact_sha256"])
    if value["quantization"] != "Q4_K_M" or value["model_role"] not in {
        "primary",
        "challenger",
    }:
        raise AdmissionPackageError(
            "runtime qualification requires admitted Q4/model role"
        )
    for key in ("context_tokens", "artifact_size_bytes", "peak_resident_memory_bytes"):
        number = value[key]
        if type(number) is not int or number <= 0:
            raise AdmissionPackageError(f"runtime {key} must be a positive integer")
    if (
        _number(value["ttft_seconds"], "TTFT") <= 0
        or _number(value["decode_tokens_per_second"], "decode throughput") <= 0
    ):
        raise AdmissionPackageError(
            "runtime timing/throughput must be measured and positive"
        )


def _positive_evidence(
    candidate: JsonObject, references: dict[str, str], root: Path, revision: str
) -> None:
    """Gate booleans cannot override failed or unrelated referenced results."""
    candidate_id = _text(candidate["candidate_id"], "candidate_id")
    gates = _object(candidate["gates"], "gates")
    selected: dict[str, list[JsonObject]] = {}
    for path in _strings(candidate["evidence_refs"], "evidence_refs"):
        kind = references[path]
        if kind in {
            "frozen-evaluation",
            "closed-loop",
            "export-parity",
            "human-ratings",
            "runtime-measurements",
        }:
            selected.setdefault(kind, []).append(load_package(root / path))
    policies: list[JsonObject] = []
    for report in selected.get("frozen-evaluation", []):
        cases = [
            _object(item, "frozen case")
            for item in _array(report.get("cases"), "cases")
        ]
        if (
            sum(_number(case.get("command_count"), "command count") for case in cases)
            == 0
        ):
            raise AdmissionPackageError(
                "positive admission requires actual frozen command execution"
            )
        policy = _object(report.get("policy"), "frozen policy")
        policies.append(policy)
        if report.get("code_revision") != revision:
            raise AdmissionPackageError("frozen evidence source revision mismatch")
        operational = _object(report.get("operational"), "frozen operational")
        mechanical = _object(operational.get("mechanical"), "frozen mechanical")
        hidden = _object(
            operational.get("hidden_information"), "frozen hidden information"
        )
        if (
            _number(mechanical.get("score"), "frozen score") < 0.95
            or _number(mechanical.get("rejection_recovery_rate"), "rejection recovery")
            < 0.8
        ):
            raise AdmissionPackageError(
                "positive admission contradicts frozen mechanical metrics"
            )
        for key in (
            "secret_leakage_count",
            "hidden_fact_use_count",
            "fabricated_result_count",
            "intercept_over_disclosure_count",
            "intercept_grounding_failure_count",
            "critical_violation_count",
        ):
            if _number(hidden.get(key), key) != 0:
                raise AdmissionPackageError(
                    "positive admission contradicts hidden-information metrics"
                )
    for report in selected.get("closed-loop", []):
        evidence = _object(report.get("evidence"), "closed-loop evidence")
        policies.append(_object(evidence.get("policy"), "closed-loop policy"))
        if (
            evidence.get("code_revision") != revision
            or evidence.get("quality_evidence") is not True
        ):
            raise AdmissionPackageError(
                "positive admission requires substantive bound closed-loop evidence"
            )
        episodes = [
            _object(item, "closed-loop episode")
            for item in _array(evidence.get("episodes"), "episodes")
        ]
        objectives, recovery = [], []
        for episode in episodes:
            metrics = _object(episode.get("metrics"), "closed-loop metrics")
            objective = _object(metrics.get("objective"), "objectives")
            failures = _object(metrics.get("recovery"), "recovery")
            hidden = _object(metrics.get("hidden_information"), "hidden information")
            objectives.append(
                _number(
                    objective.get("objective_completion_rate"), "objective completion"
                )
            )
            recovery.append(
                _number(
                    failures.get("execution_failure_recovery_rate"),
                    "execution recovery",
                )
            )
            if (
                _number(hidden.get("critical_violation_count"), "critical violations")
                != 0
            ):
                raise AdmissionPackageError(
                    "positive admission contradicts closed-loop critical violations"
                )
        if (
            not episodes
            or sum(objectives) / len(episodes) < 0.8
            or sum(recovery) / len(episodes) < 0.8
        ):
            raise AdmissionPackageError(
                "positive admission contradicts closed-loop metrics"
            )
    if (
        any(policy.get("policy_id") != candidate_id for policy in policies)
        or len({canonical_json(policy) for policy in policies}) != 1
    ):
        raise AdmissionPackageError(
            "candidate identity does not match its evaluation policies"
        )
    if any(
        value.get("passed") is not True for value in selected.get("export-parity", [])
    ):
        raise AdmissionPackageError(
            "positive admission contradicts failed export parity"
        )
    for kind, gate in (
        ("human-ratings", "human_review"),
        ("runtime-measurements", "runtime"),
    ):
        if not gates[gate]:
            continue
        for value in selected.get(kind, []):
            if value.get("candidate_id") != candidate_id:
                raise AdmissionPackageError(f"{kind} belongs to another candidate")
            if gate == "runtime":
                from .training.admission import resolve_model_binding

                primary = value["model_role"] == "primary"
                binding = resolve_model_binding("primary" if primary else "challenger")
                if candidate["base_model"] not in {
                    binding.native_repository,
                    f"{binding.native_repository}@{binding.native_revision}",
                }:
                    raise AdmissionPackageError(
                        "runtime model role contradicts candidate base model"
                    )
                if (
                    _number(value["context_tokens"], "context") < 2048
                    or _number(value["artifact_size_bytes"], "artifact size")
                    > (1_000_000_000 if primary else 3_200_000_000)
                    or _number(value["peak_resident_memory_bytes"], "resident memory")
                    > (3_000_000_000 if primary else 7_000_000_000)
                    or _number(value["ttft_seconds"], "TTFT")
                    > (2.0 if primary else 4.0)
                    or _number(value["decode_tokens_per_second"], "decode rate")
                    < (12.0 if primary else 5.0)
                ):
                    raise AdmissionPackageError(
                        "positive admission contradicts original runtime targets"
                    )


def verify_package(path: str | Path, *, evidence_root: str | Path) -> JsonObject:
    """Verify every portable reference and refuse unsupported admission claims.

    The root is explicit, rather than taken from untrusted package metadata.
    Binary artifact locations are descriptive; unavailable binaries remain explicit
    limitations and cannot support a positive admission result.
    """
    return _verify_contents(load_package(path), evidence_root=Path(evidence_root))


def _verify_contents(package: JsonObject, *, evidence_root: Path) -> JsonObject:
    _keys(
        package,
        {
            "schema",
            "schema_version",
            "programme_id",
            "code_revision",
            "outcome",
            "rationale",
            "evidence",
            "candidates",
            "data_card",
            "report",
            "limitations",
            "unavailable_artifacts",
            "content_sha256",
        },
        "package",
    )
    if package["schema"] != "ttt.final_admission" or (
        type(package["schema_version"]) is not int or package["schema_version"] != 1
    ):
        raise AdmissionPackageError("unsupported admission schema/version")
    if package["programme_id"] != "TTT-016":
        raise AdmissionPackageError("unsupported programme")
    revision = _text(package["code_revision"], "code_revision")
    if not _REVISION.fullmatch(revision):
        raise AdmissionPackageError("code_revision must be an immutable commit SHA")
    expected_hash = _sha(package["content_sha256"])
    if seal_package(package)["content_sha256"] != expected_hash:
        raise AdmissionPackageError("admission package content hash mismatch")
    outcome = _text(package["outcome"], "outcome")
    if outcome not in _OUTCOMES:
        raise AdmissionPackageError("unsupported admission outcome")
    if not _strings(package["rationale"], "rationale"):
        raise AdmissionPackageError("admission rationale is required")
    _strings(package["limitations"], "limitations")
    unavailable = _strings(package["unavailable_artifacts"], "unavailable_artifacts")

    root = Path(evidence_root).resolve()
    references: dict[str, str] = {}
    for raw_reference in _array(package["evidence"], "evidence"):
        reference = _object(raw_reference, "evidence reference")
        _keys(reference, {"path", "sha256", "kind"}, "evidence reference")
        name = _relative_path(reference["path"])
        if name in references:
            raise AdmissionPackageError(f"duplicate evidence path: {name}")
        expected = _sha(reference["sha256"])
        kind = _text(reference["kind"], "evidence kind")
        try:
            actual = evidence_reference(root, name, kind=kind)
        except OSError as exc:
            raise AdmissionPackageError(f"cannot read evidence: {name}") from exc
        if actual["sha256"] != expected:
            raise AdmissionPackageError(f"evidence hash mismatch: {name}")
        _verify_evidence_structure(root / name, kind)
        references[name] = kind
    for field in ("data_card", "report"):
        if _relative_path(package[field]) not in references:
            raise AdmissionPackageError(f"{field} must resolve to hashed evidence")

    candidate_ids: set[str] = set()
    candidate_outcomes: list[str] = []
    for raw_candidate in _array(package["candidates"], "candidates"):
        candidate = _object(raw_candidate, "candidate")
        _keys(
            candidate,
            {
                "candidate_id",
                "base_model",
                "outcome",
                "model_card",
                "evidence_refs",
                "gates",
                "constraints",
            },
            "candidate",
        )
        candidate_id = _text(candidate["candidate_id"], "candidate_id")
        if candidate_id in candidate_ids:
            raise AdmissionPackageError("duplicate candidate identity")
        candidate_ids.add(candidate_id)
        _text(candidate["base_model"], "base_model")
        if _relative_path(candidate["model_card"]) not in references:
            raise AdmissionPackageError("model card must resolve to hashed evidence")
        candidate_refs = _strings(candidate["evidence_refs"], "evidence_refs")
        if not candidate_refs or any(item not in references for item in candidate_refs):
            raise AdmissionPackageError("candidate evidence is missing or unbound")
        gates = _object(candidate["gates"], "candidate gates")
        _keys(gates, _GATES, "candidate gates")
        if any(type(value) is not bool for value in gates.values()):
            raise AdmissionPackageError("candidate gates must be boolean")
        constraints = _strings(candidate["constraints"], "constraints")
        disposition = _text(candidate["outcome"], "candidate outcome")
        if disposition not in _OUTCOMES:
            raise AdmissionPackageError("unsupported candidate outcome")
        if disposition == "ADMITTED" and not all(gates.values()):
            raise AdmissionPackageError("ADMITTED candidate has unmet gates")
        if disposition == "CONDITIONALLY ADMITTED" and (
            not all(gates[key] for key in _MANDATORY_GATES) or not constraints
        ):
            raise AdmissionPackageError(
                "conditional admission lacks safety gates/constraints"
            )
        if disposition != "NOT ADMITTED":
            kinds = {references[item] for item in candidate_refs}
            required = {
                "frozen-evaluation",
                "closed-loop",
                "export-parity",
                "provenance",
            }
            if not required <= kinds or unavailable:
                raise AdmissionPackageError(
                    "positive admission lacks verifiable evidence"
                )
            if gates["runtime"] and "runtime-measurements" not in kinds:
                raise AdmissionPackageError("runtime gate lacks measurements")
            if gates["human_review"] and "human-ratings" not in kinds:
                raise AdmissionPackageError("human gate lacks actual rating evidence")
            _positive_evidence(candidate, references, root, revision)
        candidate_outcomes.append(disposition)
    if outcome != "NOT ADMITTED" and outcome not in candidate_outcomes:
        raise AdmissionPackageError("programme outcome lacks a matching candidate")
    if outcome == "NOT ADMITTED" and any(x != outcome for x in candidate_outcomes):
        raise AdmissionPackageError(
            "negative programme outcome contradicts a candidate"
        )
    return {
        "verified": True,
        "outcome": outcome,
        "content_sha256": expected_hash,
        "verified_files": len(references),
        "candidate_count": len(candidate_ids),
        "unavailable_artifacts": [item for item in unavailable],
    }


def write_package(
    path: Path, package: JsonObject, *, evidence_root: Path
) -> JsonObject:
    """Write a sealed package only after its actual referenced files are present."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sealed = seal_package(package)
    result = _verify_contents(sealed, evidence_root=evidence_root)
    path.write_text(canonical_json(sealed) + "\n", encoding="utf-8", newline="\n")
    return result
