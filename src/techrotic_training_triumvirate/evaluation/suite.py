"""Integrity-checked loader for the immutable TTT benchmark v1 suite."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import cast

from techrotic_training_triumvirate.schemas import JsonObject, PersonaSpec, content_hash

from .model import BenchmarkCase, BenchmarkManifest

BENCHMARK_RESOURCE = "benchmark_v1.json"
EXPECTED_BENCHMARK_HASH = (
    "22a93e8861e25d1b6b15fea298431b4023b28610884d1699d447cf8a85bb92aa"
)


class BenchmarkIntegrityError(ValueError):
    """Raised when a frozen benchmark changes without a version/hash update."""


def _object(value: object, *, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BenchmarkIntegrityError(f"{where} must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise BenchmarkIntegrityError(f"{where} keys must be strings")
        result[key] = item
    return result


def _array(value: object, *, where: str) -> list[object]:
    if not isinstance(value, list):
        raise BenchmarkIntegrityError(f"{where} must be an array")
    return cast(list[object], value)


def _string(value: object, *, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkIntegrityError(f"{where} must be a non-empty string")
    return value


def _integer(value: object, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BenchmarkIntegrityError(f"{where} must be an integer")
    return value


def _boolean(value: object, *, where: str) -> bool:
    if not isinstance(value, bool):
        raise BenchmarkIntegrityError(f"{where} must be a boolean")
    return value


def _exact_keys(value: dict[str, object], expected: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != expected:
        raise BenchmarkIntegrityError(
            f"{where} fields differ: expected {sorted(expected)}, got {sorted(actual)}"
        )


def _json_object(value: object, *, where: str) -> JsonObject:
    raw = _object(value, where=where)
    # The benchmark file is JSON-decoded; this cast narrows an already checked object.
    return cast(JsonObject, raw)


def _case(value: object, *, suite: str, index: int) -> BenchmarkCase:
    raw = _object(value, where=f"{suite}[{index}]")
    _exact_keys(
        raw,
        {
            "case_id",
            "family",
            "seed",
            "kind",
            "complexity",
            "unit_count",
            "mid_state",
            "turns",
        },
        where=f"{suite}[{index}]",
    )
    complexity = _integer(raw["complexity"], where="complexity")
    family = _string(raw["family"], where="family")
    if family != f"abstract-c{complexity}":
        raise BenchmarkIntegrityError(
            f"{suite}[{index}] family does not match ScenarioGenerator complexity"
        )
    return BenchmarkCase(
        case_id=_string(raw["case_id"], where="case_id"),
        suite=suite,
        kind=_string(raw["kind"], where="kind"),
        family=family,
        seed=_integer(raw["seed"], where="seed"),
        complexity=complexity,
        unit_count=_integer(raw["unit_count"], where="unit_count"),
        mid_state=_boolean(raw["mid_state"], where="mid_state"),
        turns=_integer(raw["turns"], where="turns"),
    )


def _persona(value: object) -> PersonaSpec:
    raw = _object(value, where="persona")
    _exact_keys(
        raw,
        {
            "persona_id",
            "archetype",
            "speech_constraints",
            "doctrine",
            "secret_ids",
        },
        where="persona",
    )
    speech = tuple(
        _string(item, where=f"speech_constraints[{index}]")
        for index, item in enumerate(
            _array(raw["speech_constraints"], where="speech_constraints")
        )
    )
    secret_ids = tuple(
        _string(item, where=f"secret_ids[{index}]")
        for index, item in enumerate(_array(raw["secret_ids"], where="secret_ids"))
    )
    return PersonaSpec(
        persona_id=_string(raw["persona_id"], where="persona_id"),
        archetype=_string(raw["archetype"], where="archetype"),
        traits={},
        speech_constraints=speech,
        doctrine=_json_object(raw["doctrine"], where="doctrine"),
        secret_ids=secret_ids,
        tactical_biases={},
    )


def _validate_reservations(value: object, cases: tuple[BenchmarkCase, ...]) -> None:
    reservations = _array(value, where="reservations")
    parsed: list[tuple[str, str, int]] = []
    for index, item in enumerate(reservations):
        raw = _object(item, where=f"reservations[{index}]")
        _exact_keys(
            raw,
            {"case_id", "family", "seed"},
            where=f"reservations[{index}]",
        )
        parsed.append(
            (
                _string(raw["case_id"], where="case_id"),
                _string(raw["family"], where="family"),
                _integer(raw["seed"], where="seed"),
            )
        )
    expected = [(case.case_id, case.family, case.seed) for case in cases]
    if parsed != expected:
        raise BenchmarkIntegrityError(
            "reservations must exactly match all frozen case family/seed identities"
        )


@lru_cache(maxsize=1)
def load_benchmark_v1() -> BenchmarkManifest:
    """Load and verify the committed frozen v1 benchmark manifest."""
    text = (
        resources.files("techrotic_training_triumvirate.evaluation")
        .joinpath(BENCHMARK_RESOURCE)
        .read_text(encoding="utf-8")
    )
    raw_value = cast(object, json.loads(text))
    raw = _object(raw_value, where="benchmark")
    _exact_keys(
        raw,
        {
            "benchmark_id",
            "benchmark_version",
            "suite_format",
            "persona",
            "generated",
            "adversarial",
            "reservations",
        },
        where="benchmark",
    )
    if _integer(raw["suite_format"], where="suite_format") != 1:
        raise BenchmarkIntegrityError("unsupported benchmark suite format")

    actual_hash = content_hash(raw)
    if actual_hash != EXPECTED_BENCHMARK_HASH:
        raise BenchmarkIntegrityError(
            "frozen benchmark v1 content changed; create a new benchmark version "
            f"instead (expected {EXPECTED_BENCHMARK_HASH}, got {actual_hash})"
        )

    generated = tuple(
        _case(item, suite="generated", index=index)
        for index, item in enumerate(_array(raw["generated"], where="generated"))
    )
    adversarial = tuple(
        _case(item, suite="adversarial", index=index)
        for index, item in enumerate(_array(raw["adversarial"], where="adversarial"))
    )
    cases = generated + adversarial
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise BenchmarkIntegrityError("benchmark case IDs must be unique")
    reservations = [(case.family, case.seed) for case in cases]
    if len(reservations) != len(set(reservations)):
        raise BenchmarkIntegrityError("frozen family/seed reservations must be unique")
    _validate_reservations(raw["reservations"], cases)

    return BenchmarkManifest(
        benchmark_id=_string(raw["benchmark_id"], where="benchmark_id"),
        benchmark_version=_string(raw["benchmark_version"], where="benchmark_version"),
        manifest_hash=actual_hash,
        generated=generated,
        adversarial=adversarial,
        persona=_persona(raw["persona"]),
    )
