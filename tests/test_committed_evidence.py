"""The delivered study must remain readable without models, CUDA or downloads."""

from __future__ import annotations

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
