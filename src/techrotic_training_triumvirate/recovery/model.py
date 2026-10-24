"""Dependency-light records for student-visited corrective rollouts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommanderObservation,
    InterpreterResult,
    JsonObject,
)


class FailureCategory(str, Enum):
    """Stable corrective-rollout failure categories."""

    COMMAND_SCHEMA = "command.schema"
    COMMAND_PROTOCOL = "command.protocol"
    COMMAND_ENTITY = "command.entity"
    COMMAND_CAPABILITY = "command.capability"
    COMMAND_TARGET = "command.target"
    COMMAND_PRECONDITION = "command.precondition"
    COMMAND_RESOURCE = "command.resource"
    COMMAND_STALE = "command.stale"
    COMMAND_CONFLICT = "command.conflict"
    EXECUTION_ROUTE = "execution.route"
    EXECUTION_STALL = "execution.stall"
    EXECUTION_RESOURCE = "execution.resource"
    EXECUTION_TARGET = "execution.target"
    EXECUTION_UNIT_LOST = "execution.unit_lost"
    EXECUTION_OTHER = "execution.other"


@dataclass(frozen=True, slots=True)
class ScriptedStep:
    """One deterministic command-body template for ScriptedStudentAdapter."""

    command_body: JsonObject
    generation_offset: int = 0
    communication_text: str | None = None
    communication_channel: str = "command"

    def __post_init__(self) -> None:
        if self.communication_text is not None and not self.communication_text.strip():
            raise ValueError("communication_text must be null or non-empty")
        if not self.communication_channel.strip():
            raise ValueError("communication_channel must not be empty")


@dataclass(frozen=True, slots=True)
class FailurePoint:
    """Authoritative failure evidence from one student-visited turn."""

    turn_id: int
    attempt_id: str
    command_id: str
    category: FailureCategory
    code: str
    observation: CommanderObservation
    action: AssistantAction
    interpreter_results: tuple[InterpreterResult, ...]
    world_events: tuple[AuthoritativeEvent, ...]

    def __post_init__(self) -> None:
        if self.turn_id < 0:
            raise ValueError("turn_id must be non-negative")
        for name, value in (
            ("attempt_id", self.attempt_id),
            ("command_id", self.command_id),
            ("code", self.code),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")

    def to_summary(self) -> JsonObject:
        return {
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "command_id": self.command_id,
            "category": self.category.value,
            "code": self.code,
            "observation_hash": self.observation.content_hash(),
            "action_hash": self.action.content_hash(),
            "result_hashes": [
                result.content_hash() for result in self.interpreter_results
            ],
            "event_hashes": [event.content_hash() for event in self.world_events],
        }


@dataclass(frozen=True, slots=True)
class RecoveryRunConfig:
    """Identity and bounds for one deterministic corrective rollout round."""

    run_id: str
    git_commit: str
    seed: int
    turns: int = 3
    iteration: int = 0
    parent_run_id: str | None = None
    alternatives_per_failure: int = 1
    mid_state: bool = False
    corpus_dev_percent: int = 0

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty")
        if not self.git_commit.strip():
            raise ValueError("git_commit must not be empty")
        if self.turns < 1:
            raise ValueError("turns must be positive")
        if self.iteration < 0:
            raise ValueError("iteration must be non-negative")
        if self.parent_run_id is not None and not self.parent_run_id.strip():
            raise ValueError("parent_run_id must be null or non-empty")
        if self.alternatives_per_failure < 1:
            raise ValueError("alternatives_per_failure must be positive")
        if not 0 <= self.corpus_dev_percent <= 100:
            raise ValueError("corpus_dev_percent must be between 0 and 100")
