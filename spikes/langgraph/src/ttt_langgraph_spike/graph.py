"""LangGraph orchestration proof around the tiny deterministic TTT world."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from .world import (
    SpikeState,
    apply_command,
    blocked_direct_command,
    commander_observation,
    corrected_flank_command,
    initial_state,
)


def _observe(state: SpikeState) -> dict[str, Any]:
    return {"observation": commander_observation(state["world"])}


def _apply_command(state: SpikeState) -> dict[str, Any]:
    world, result, events = apply_command(state["world"], state["command"])
    return {
        "world": world,
        "observation": commander_observation(world),
        "result": result,
        "events": events,
    }


def build_graph(checkpointer: InMemorySaver | None = None):
    """Compile the minimal workflow with explicit checkpoint persistence."""
    builder = StateGraph(SpikeState)
    builder.add_node("observe", _observe)
    builder.add_node("apply_command", _apply_command)
    builder.add_edge(START, "observe")
    builder.add_edge("observe", "apply_command")
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def semantic_projection(state: Mapping[str, Any]) -> dict[str, Any]:
    """Project only TTT semantic state, excluding LangGraph checkpoint metadata."""
    return {
        "world": state["world"],
        "observation": state["observation"],
        "command": state["command"],
        "result": state["result"],
        "events": state["events"],
    }


def semantic_hash(state: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        semantic_projection(state),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _checkpoint_id(config: Mapping[str, Any]) -> str:
    return str(config["configurable"]["checkpoint_id"])


def run_demo(thread_id: str = "ttt-langgraph-spike") -> dict[str, Any]:
    """Execute failure -> historical correction branch -> replay proof."""
    graph = build_graph()
    config = thread_config(thread_id)

    original = graph.invoke(initial_state(blocked_direct_command()), config)
    original_final = graph.get_state(config)

    before_apply = next(
        snapshot
        for snapshot in graph.get_state_history(config)
        if snapshot.next == ("apply_command",)
    )

    branch_config = graph.update_state(
        before_apply.config,
        {
            "command": corrected_flank_command(),
            "result": None,
            "events": [],
        },
    )
    branch_checkpoint = graph.get_state(branch_config)

    corrected = graph.invoke(None, branch_config)

    # Supplying the same historical branch checkpoint re-executes the nodes after
    # that checkpoint. This is a replay of the corrected branch point, not a
    # continuation from the newest thread head.
    replayed = graph.invoke(None, branch_config)

    # The original failed final checkpoint is addressed by its immutable config
    # even after new branches have been added to the same thread history.
    original_readback = graph.get_state(original_final.config).values

    return {
        "langgraph_checkpoint_before_apply": _checkpoint_id(before_apply.config),
        "langgraph_branch_checkpoint": _checkpoint_id(branch_checkpoint.config),
        "langgraph_original_final_checkpoint": _checkpoint_id(original_final.config),
        "original": original,
        "original_readback": original_readback,
        "corrected": corrected,
        "replayed": replayed,
        "original_hash": semantic_hash(original),
        "original_readback_hash": semantic_hash(original_readback),
        "corrected_hash": semantic_hash(corrected),
        "replayed_hash": semantic_hash(replayed),
    }
