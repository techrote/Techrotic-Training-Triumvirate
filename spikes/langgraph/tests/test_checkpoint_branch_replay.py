from __future__ import annotations

from ttt_langgraph_spike import (
    blocked_direct_command,
    build_graph,
    corrected_flank_command,
    initial_state,
    run_demo,
)
from ttt_langgraph_spike.graph import semantic_hash, thread_config


def test_blocked_command_fails_without_mutating_authoritative_world() -> None:
    graph = build_graph()
    config = thread_config("blocked-no-mutation")
    start = initial_state(blocked_direct_command())

    result = graph.invoke(start, config)

    assert result["result"] == {
        "accepted": False,
        "code": "ROUTE_BLOCKED",
        "detail": "Route direct is blocked.",
    }
    assert result["world"] == start["world"]
    assert result["world"]["relay_secured"] is False


def test_commander_observation_excludes_private_world_fact() -> None:
    graph = build_graph()
    result = graph.invoke(
        initial_state(blocked_direct_command()),
        thread_config("visibility"),
    )

    assert "private_fact" in result["world"]
    assert "private_fact" not in result["observation"]
    assert "relay-backup-generator-online" not in repr(result["observation"])


def test_checkpoint_branch_correction_replay_and_original_readback() -> None:
    evidence = run_demo("checkpoint-branch-correction-replay")

    assert evidence["original"]["result"]["code"] == "ROUTE_BLOCKED"
    assert evidence["original"]["world"]["relay_secured"] is False

    assert evidence["corrected"]["command"] == corrected_flank_command()
    assert evidence["corrected"]["result"]["code"] == "OK"
    assert evidence["corrected"]["world"]["relay_secured"] is True

    assert (
        evidence["langgraph_checkpoint_before_apply"]
        != evidence["langgraph_branch_checkpoint"]
    )
    assert (
        evidence["langgraph_original_final_checkpoint"]
        != evidence["langgraph_branch_checkpoint"]
    )

    assert evidence["corrected_hash"] == evidence["replayed_hash"]
    assert semantic_hash(evidence["corrected"]) == semantic_hash(evidence["replayed"])

    assert evidence["original_hash"] == evidence["original_readback_hash"]
    assert evidence["original_readback"]["result"]["code"] == "ROUTE_BLOCKED"
    assert evidence["original_readback"]["world"]["relay_secured"] is False


def test_repeated_demo_is_semantically_deterministic_across_threads() -> None:
    first = run_demo("determinism-a")
    second = run_demo("determinism-b")

    assert first["original_hash"] == second["original_hash"]
    assert first["corrected_hash"] == second["corrected_hash"]
    assert first["replayed_hash"] == second["replayed_hash"]
