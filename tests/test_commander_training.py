"""Aligned data must preserve model responsibility and the authority boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.training.commander import (
    decode_action,
    encode_action,
    generate_demonstrations,
    map_commander,
)
from techrotic_training_triumvirate.training.data import load_corpus_examples


def test_wire_codec_does_not_repair_model_tactics_or_stale_generations() -> None:
    body = {
        "op": "assign_objective",
        "observation_generation": 999,
        "unit_id": "wrong-unit",
        "target_id": "wrong-objective",
        "approach": "direct",
        "constraints": [],
        "objective_kind": "secure",
    }
    action = decode_action(
        json.dumps({"command": body, "speech": "Keep watch."}), record_id="wire"
    )
    assert action.commands[0].body == body
    assert action.commands[0].command_id == "wire:command"
    assert json.loads(encode_action(action))["command"] == body


@pytest.mark.parametrize(
    "reply",
    [
        "not JSON",
        '{"command":{},"speech":"a","speech":"b"}',
        '{"command":{},"speech":"a","outcome":"success"}',
        '{"command":{},"speech":""}',
    ],
)
def test_bad_model_reply_is_rejected_without_oracle_fallback(reply: str) -> None:
    action = decode_action(reply, record_id="bad")
    assert action.commands[0].body == {"op": "invalid_model_output"}
    assert action.communications == ()


def test_aligned_corpus_is_deterministic_disjoint_and_excludes_environment_probes(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    identity = generate_demonstrations(first, git_commit="a" * 40, episodes=8)
    assert generate_demonstrations(second, git_commit="a" * 40, episodes=8) == identity
    sources, readback = load_corpus_examples(first)
    assert readback.to_object() == identity
    train = {e.example_id.split(":")[0] for e in sources if e.split == "train"}
    dev = {e.example_id.split(":")[0] for e in sources if e.split == "dev"}
    assert train and dev and train.isdisjoint(dev)
    assert (first / "source-episodes.jsonl").read_bytes() == (
        second / "source-episodes.jsonl"
    ).read_bytes()
    for source in sources:
        mapped = map_commander(source)
        assert json.loads(mapped.prompt_messages[1].content) == source.input
        body = json.loads(mapped.assistant_target)["command"]
        assert "simulate:stall" not in str(body)
        assert body["observation_generation"] == source.input["observation_generation"]
        assert "case_id" not in source.input
        assert "evaluator_only" not in source.input
    assert any("execution-failed" in str(e.input["events"]) for e in sources)
    assert any("CAPABILITY_MISMATCH" in str(e.input["feedback"]) for e in sources)


def test_frozen_world_is_refused_before_training_data_generation(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        generate_demonstrations(
            tmp_path / "refused", git_commit="a" * 40, episodes=1, seed=240901
        )
