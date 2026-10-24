from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from techrotic_training_triumvirate.commands import (  # noqa: E402
    AssignObjectiveCommand,
    RequestStatusCommand,
)
from techrotic_training_triumvirate.session import SessionRecording  # noqa: E402
from techrotic_training_triumvirate.session.langgraph_backend import (  # noqa: E402
    LangGraphSession,
)


def _original_commands() -> tuple:
    return (
        AssignObjectiveCommand(
            command_id="branch-route",
            observation_generation=0,
            unit_id="unit-1",
            objective_kind="secure",
            target_id="relay-east",
            approach="direct",
            constraints=(),
        ).to_envelope(),
        RequestStatusCommand(
            command_id="branch-status",
            observation_generation=1,
            entity_ids=("unit-1", "relay-east"),
        ).to_envelope(),
    )


def test_recording_replays_with_ttt_hashes_and_checkpoint_replay() -> None:
    base = SessionRecording.new(
        session_id="session-replay",
        run_id="run-replay",
        seed=24301,
    )
    graph = LangGraphSession()
    recorded = graph.run_commands(
        base,
        _original_commands(),
        thread_id="record-session",
    )

    verifier = LangGraphSession()
    evidence = verifier.verify_recording(
        recorded,
        thread_id="verify-session",
    )

    assert evidence.semantic_hash == recorded.semantic_hash()
    assert evidence.final_world_hash == recorded.final_world_hash
    assert evidence.checkpoint_id
    assert evidence.replay_checkpoint_id
    assert tuple(turn.turn_hash for turn in recorded.turns) == tuple(
        turn.turn_hash for turn in SessionRecording.from_dict(recorded.to_dict()).turns
    )


def test_historical_correction_branches_without_mutating_original_recording() -> None:
    base = SessionRecording.new(
        session_id="session-branch",
        run_id="run-branch",
        seed=24301,
    )
    graph = LangGraphSession()
    original = graph.run_commands(
        base,
        _original_commands(),
        thread_id="branch-session",
    )
    corrected = AssignObjectiveCommand(
        command_id="branch-route",
        observation_generation=0,
        unit_id="unit-1",
        objective_kind="secure",
        target_id="relay-east",
        approach="north",
        constraints=(),
    ).to_envelope()

    branch = graph.branch_correction(
        thread_id="branch-session",
        original_command_id="branch-route",
        corrected_command=corrected,
        branch_id="correction-1",
    )

    assert branch.original_recording_hash == original.semantic_hash()
    assert branch.recording.branch_id == "correction-1"
    assert branch.recording.parent_branch_id == "main"
    assert branch.recording.parent_turn_id == 0
    assert branch.recording.parent_turn_hash == base.initial_observation.content_hash()
    assert branch.branch_checkpoint_id != branch.original_checkpoint_id
    assert len(branch.recording.turns) == 1
    assert branch.recording.turns[0].action.commands[0] == corrected
    assert all(
        event.data.get("code") != "ROUTE_BLOCKED"
        for event in branch.recording.turns[0].events
    )


def test_checkpoint_ids_are_supplementary_not_semantic_identity() -> None:
    command = RequestStatusCommand(
        command_id="identity-status",
        observation_generation=0,
        entity_ids=("unit-1",),
    ).to_envelope()
    first_graph = LangGraphSession()
    second_graph = LangGraphSession()
    first = first_graph.run_commands(
        SessionRecording.new(
            session_id="same-session",
            run_id="same-run",
            seed=10,
        ),
        (command,),
        thread_id="identity-a",
    )
    second = second_graph.run_commands(
        SessionRecording.new(
            session_id="same-session",
            run_id="same-run",
            seed=10,
        ),
        (command,),
        thread_id="identity-b",
    )

    assert first.checkpoint_refs
    assert second.checkpoint_refs
    assert first.semantic_hash() == second.semantic_hash()
    assert first.turns[0].turn_hash == second.turns[0].turn_hash
