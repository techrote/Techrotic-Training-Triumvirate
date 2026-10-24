"""The delivered study must remain readable without models, CUDA or downloads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from techrotic_training_triumvirate.admission import load_package, verify_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs/evidence/ttt-016/admission-package.json"


def test_committed_final_package_and_all_four_candidates_read_back() -> None:
    result = verify_package(PACKAGE, evidence_root=ROOT)
    assert result["verified"] is True
    assert result["outcome"] == "NOT ADMITTED"
    assert result["candidate_count"] == 4
    package = load_package(PACKAGE)
    references = {item["path"]: item["kind"] for item in package["evidence"]}
    assert {item["candidate_id"] for item in package["candidates"]} == {
        "pilot-operational",
        "pilot-persona",
        "pilot-joint",
        "pilot-joint-corrective",
    }
    for candidate in package["candidates"]:
        assert candidate["gates"]["export_parity"] is True
        assert candidate["gates"]["closed_loop"] is False
        assert candidate["gates"]["human_review"] is False
        assert candidate["gates"]["runtime"] is False
        frozen = [
            path
            for path in candidate["evidence_refs"]
            if references[path] == "frozen-evaluation"
        ]
        closed = [
            path
            for path in candidate["evidence_refs"]
            if references[path] == "closed-loop"
        ]
        assert len(frozen) == len(closed) == 1
        assert (
            load_package(ROOT / frozen[0])["policy"]["policy_id"]
            == candidate["candidate_id"]
        )
        evidence = load_package(ROOT / closed[0])["evidence"]
        assert evidence["policy"]["policy_id"] == candidate["candidate_id"]
        assert len(evidence["episodes"]) == 3
        assert all(len(episode["turns"]) == 24 for episode in evidence["episodes"])


def test_committed_blinded_packet_has_no_invented_human_ratings() -> None:
    packet = load_package(ROOT / "docs/evidence/ttt-016/human-packet.json")
    assert packet["samples"]
    for sample in packet["samples"]:
        assert all(value is None for value in sample["human_ratings"].values())


def test_rejected_continuation_development_replays_all_actual_actions() -> None:
    from techrotic_training_triumvirate.evaluation import (
        PolicyIdentity,
        load_benchmark_v1,
        run_benchmark,
    )
    from techrotic_training_triumvirate.schemas import (
        AssistantAction,
        content_hash,
        load_record,
    )

    folder = ROOT / "docs/evidence/ttt-017/attempt-03"
    names = set()
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
        names.add(name)
    assert names == {p.name for p in folder.iterdir() if p.name != "SHA256SUMS"}
    stored = load_package(folder / "development.json")
    rows = [
        json.loads(line)
        for line in (folder / "raw-generations.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 77
    actions = {
        (r["case_id"], r["turn"]): load_record(
            r["action"], expected_type=AssistantAction
        )
        for r in rows
    }

    class Recorded:
        identity = PolicyIdentity(**stored["policy"])

        def begin_case(self, *, case_id, seed):
            pass

        def act(self, context):
            return actions[(context.case_id, context.turn_index)]

    original = load_benchmark_v1()
    cases = tuple(
        replace(c, case_id=f"development-{i}", seed=960000 + i)
        for i, c in enumerate(original.cases)
    )
    manifest = replace(
        original,
        benchmark_id="ttt-development-v2",
        manifest_hash=content_hash([{"seed": c.seed, "kind": c.kind} for c in cases]),
        generated=tuple(c for c in cases if c.suite == "generated"),
        adversarial=tuple(c for c in cases if c.suite == "adversarial"),
    )
    replay = run_benchmark(
        Recorded(), code_revision=stored["code_revision"], manifest=manifest
    ).to_dict()
    assert replay == stored
    assert stored["operational"]["mechanical"]["score"] < 0.95
    assert stored["operational"]["mechanical"]["rejection_recovery_rate"] < 0.8
    assert not (folder / "benchmark.json").exists()
