"""Optional LangGraph orchestration backend for TTT semantic sessions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypedDict, cast

from langgraph.checkpoint.memory import InMemorySaver  # type: ignore[import-not-found]
from langgraph.graph import START, StateGraph  # type: ignore[import-not-found]

from techrotic_training_triumvirate.schemas import (
    CommandEnvelope,
    JsonObject,
    SchemaValidationError,
    load_record,
)

from .recording import SessionRecording, execute_turn


class SessionGraphState(TypedDict, total=False):
    recording: JsonObject
    next_command: JsonObject | None


@dataclass(frozen=True, slots=True)
class ReplayVerification:
    semantic_hash: str
    final_world_hash: str
    checkpoint_id: str
    replay_checkpoint_id: str


@dataclass(frozen=True, slots=True)
class BranchResult:
    recording: SessionRecording
    branch_checkpoint_id: str
    original_checkpoint_id: str
    original_recording_hash: str


def _checkpoint_id(config: Mapping[str, Any]) -> str:
    configurable = config.get("configurable")
    if not isinstance(configurable, Mapping):
        raise SchemaValidationError("LangGraph checkpoint config missing configurable")
    checkpoint_id = configurable.get("checkpoint_id")
    if not isinstance(checkpoint_id, str):
        raise SchemaValidationError("LangGraph checkpoint config missing checkpoint_id")
    return checkpoint_id


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _execute_turn_node(state: SessionGraphState) -> SessionGraphState:
    recording_raw = state.get("recording")
    command_raw = state.get("next_command")
    if recording_raw is None:
        raise SchemaValidationError("session graph state missing recording")
    if command_raw is None:
        raise SchemaValidationError("session graph state missing next_command")
    recording = SessionRecording.from_dict(recording_raw)
    envelope = cast(
        CommandEnvelope,
        load_record(command_raw, expected_type=CommandEnvelope),
    )
    updated = execute_turn(recording, envelope)
    return {
        "recording": updated.to_dict(),
        "next_command": None,
    }


class LangGraphSession:
    """Own LangGraph checkpoint mechanics without making them semantic identity."""

    def __init__(self, checkpointer: InMemorySaver | None = None) -> None:
        builder = StateGraph(SessionGraphState)
        builder.add_node("execute_turn", _execute_turn_node)
        builder.add_edge(START, "execute_turn")
        self.graph = builder.compile(checkpointer=checkpointer or InMemorySaver())

    def run_commands(
        self,
        recording: SessionRecording,
        commands: tuple[CommandEnvelope, ...],
        *,
        thread_id: str,
    ) -> SessionRecording:
        config = thread_config(thread_id)
        current = recording
        for envelope in commands:
            result = self.graph.invoke(
                {
                    "recording": current.to_dict(),
                    "next_command": envelope.to_dict(),
                },
                config,
            )
            current = SessionRecording.from_dict(result["recording"])
            checkpoint = self.graph.get_state(config)
            current = current.with_checkpoint_ref(_checkpoint_id(checkpoint.config))
        return current

    def _checkpoint_before_command(
        self,
        *,
        thread_id: str,
        command_id: str,
    ) -> Any:
        config = thread_config(thread_id)
        for snapshot in self.graph.get_state_history(config):
            values = snapshot.values
            if not isinstance(values, Mapping):
                continue
            raw = values.get("next_command")
            if not isinstance(raw, dict):
                continue
            try:
                envelope = cast(
                    CommandEnvelope,
                    load_record(raw, expected_type=CommandEnvelope),
                )
            except ValueError:
                continue
            if envelope.command_id == command_id and snapshot.next == ("execute_turn",):
                return snapshot
        raise LookupError(f"no checkpoint found before command {command_id}")

    def verify_recording(
        self,
        recording: SessionRecording,
        *,
        thread_id: str,
    ) -> ReplayVerification:
        """Re-execute exact commands and replay the final historical checkpoint."""
        commands = tuple(
            turn.action.commands[0]
            for turn in recording.turns
            if len(turn.action.commands) == 1
        )
        if len(commands) != len(recording.turns):
            raise SchemaValidationError(
                "session v1 replay requires exactly one command per turn"
            )
        fresh = SessionRecording.new(
            session_id=recording.session_id,
            run_id=recording.run_id,
            seed=recording.seed,
            mid_state=recording.mid_state,
            branch_id=recording.branch_id,
        )
        if recording.parent_branch_id is not None:
            fresh = SessionRecording(
                session_id=fresh.session_id,
                run_id=fresh.run_id,
                branch_id=recording.branch_id,
                parent_branch_id=recording.parent_branch_id,
                parent_turn_id=recording.parent_turn_id,
                parent_turn_hash=recording.parent_turn_hash,
                seed=fresh.seed,
                mid_state=fresh.mid_state,
                scenario=fresh.scenario,
                initial_world=fresh.initial_world,
                initial_observation=fresh.initial_observation,
                turns=(),
                checkpoint_refs=(),
            )
        reproduced = self.run_commands(fresh, commands, thread_id=thread_id)
        if tuple(turn.turn_hash for turn in reproduced.turns) != tuple(
            turn.turn_hash for turn in recording.turns
        ):
            raise SchemaValidationError(
                "replayed TTT turn hashes do not match recording"
            )
        if reproduced.final_world_hash != recording.final_world_hash:
            raise SchemaValidationError(
                "replayed final world hash does not match recording"
            )
        if not commands:
            raise SchemaValidationError("checkpoint replay requires at least one turn")
        before_last = self._checkpoint_before_command(
            thread_id=thread_id,
            command_id=commands[-1].command_id,
        )
        replayed_state = self.graph.invoke(None, before_last.config)
        replayed = SessionRecording.from_dict(replayed_state["recording"])
        if replayed.turns[-1].turn_hash != recording.turns[-1].turn_hash:
            raise SchemaValidationError("historical checkpoint replay hash mismatch")
        if replayed.final_world_hash != recording.final_world_hash:
            raise SchemaValidationError(
                "historical checkpoint replay world hash mismatch"
            )
        replay_final = self.graph.get_state(thread_config(thread_id))
        return ReplayVerification(
            semantic_hash=recording.semantic_hash(),
            final_world_hash=recording.final_world_hash,
            checkpoint_id=_checkpoint_id(before_last.config),
            replay_checkpoint_id=_checkpoint_id(replay_final.config),
        )

    def branch_correction(
        self,
        *,
        thread_id: str,
        original_command_id: str,
        corrected_command: CommandEnvelope,
        branch_id: str,
        original_checkpoint_id: str | None = None,
    ) -> BranchResult:
        """Correct one historical command without mutating its original final state."""
        config = thread_config(thread_id)
        original_config = config
        if original_checkpoint_id is not None:
            original_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": original_checkpoint_id,
                }
            }
        original_final = self.graph.get_state(original_config)
        original_values = original_final.values
        if not isinstance(original_values, Mapping):
            raise SchemaValidationError("LangGraph final state is not a mapping")
        original_recording_raw = original_values.get("recording")
        if not isinstance(original_recording_raw, dict):
            raise SchemaValidationError("LangGraph final state missing recording")
        original_recording = SessionRecording.from_dict(original_recording_raw)

        before = self._checkpoint_before_command(
            thread_id=thread_id,
            command_id=original_command_id,
        )
        values = before.values
        if not isinstance(values, Mapping):
            raise SchemaValidationError(
                "historical checkpoint values are not a mapping"
            )
        prefix_raw = values.get("recording")
        if not isinstance(prefix_raw, dict):
            raise SchemaValidationError("historical checkpoint missing recording")
        prefix = SessionRecording.from_dict(prefix_raw)
        branched = prefix.as_branch(
            branch_id=branch_id,
            parent_turn_id=len(prefix.turns),
        )
        branch_config = self.graph.update_state(
            before.config,
            {
                "recording": branched.to_dict(),
                "next_command": corrected_command.to_dict(),
            },
        )
        branch_checkpoint = self.graph.get_state(branch_config)
        corrected_state = self.graph.invoke(None, branch_config)
        corrected = SessionRecording.from_dict(corrected_state["recording"])

        original_readback = self.graph.get_state(original_final.config).values
        if not isinstance(original_readback, Mapping):
            raise SchemaValidationError("original checkpoint readback is not a mapping")
        original_readback_raw = original_readback.get("recording")
        if not isinstance(original_readback_raw, dict):
            raise SchemaValidationError(
                "original checkpoint readback missing recording"
            )
        if SessionRecording.from_dict(original_readback_raw).semantic_hash() != (
            original_recording.semantic_hash()
        ):
            raise SchemaValidationError("original branch changed after correction")
        return BranchResult(
            recording=corrected,
            branch_checkpoint_id=_checkpoint_id(branch_checkpoint.config),
            original_checkpoint_id=_checkpoint_id(original_final.config),
            original_recording_hash=original_recording.semantic_hash(),
        )
