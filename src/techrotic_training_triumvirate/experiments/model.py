"""Strict identities and durable records for deterministic experiment orchestration."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast
from uuid import UUID

from techrotic_training_triumvirate.schemas import JsonObject, JsonValue, content_hash


class ExperimentContractError(ValueError):
    """An experiment plan or externally supplied event violates its contract."""


class EvidenceClass(StrEnum):
    """Whether an artifact is eligible to participate in real admission."""

    ADMISSION = "admission"
    SIMULATION = "simulation"
    CPU_DIAGNOSTIC = "cpu-diagnostic"


class ExperimentState(StrEnum):
    PLANNED = "PLANNED"
    PREFLIGHT = "PREFLIGHT"
    READY = "READY"
    TRAINING = "TRAINING"
    TRAINED = "TRAINED"
    DEVELOPMENT = "DEVELOPMENT"
    CANDIDATE_SELECTED = "CANDIDATE_SELECTED"
    EXPORTING = "EXPORTING"
    RUNTIME_QUALIFICATION = "RUNTIME_QUALIFICATION"
    FROZEN_EVALUATION = "FROZEN_EVALUATION"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    ADMISSION_READBACK = "ADMISSION_READBACK"
    COMPLETE = "COMPLETE"
    CANCELLING = "CANCELLING"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    NEEDS_ENGINEERING = "NEEDS_ENGINEERING"


class EventKind(StrEnum):
    PLAN_VALIDATED = "PLAN_VALIDATED"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    WORKER_LAUNCHED = "WORKER_LAUNCHED"
    TRAINING_VERIFIED = "TRAINING_VERIFIED"
    DEVELOPMENT_STARTED = "DEVELOPMENT_STARTED"
    DEVELOPMENT_PASSED = "DEVELOPMENT_PASSED"
    EXPORT_STARTED = "EXPORT_STARTED"
    EXPORT_VERIFIED = "EXPORT_VERIFIED"
    RUNTIME_PASSED = "RUNTIME_PASSED"
    FROZEN_PASSED = "FROZEN_PASSED"
    HUMAN_REVIEW_IMPORTED = "HUMAN_REVIEW_IMPORTED"
    ADMISSION_VERIFIED = "ADMISSION_VERIFIED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    ENGINEERING_REQUIRED = "ENGINEERING_REQUIRED"


def _sha256(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ExperimentContractError(f"{field} must be a lowercase SHA-256")
    return value


def _git_sha(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ExperimentContractError("semantic_commit must be a full Git SHA")
    return value


def _positive_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentContractError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ExperimentContractError(f"{field} must be finite and positive")
    return result


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExperimentContractError(f"{field} must be a non-empty string")
    return value


def _gpu_uuid(value: object) -> str:
    text = _text(value, field="gpu_uuid")
    try:
        parsed = UUID(text.removeprefix("GPU-"))
    except ValueError as exc:
        raise ExperimentContractError(
            "gpu_uuid must be a full physical GPU UUID"
        ) from exc
    return f"GPU-{parsed}"


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    """Immutable execution plan. Its ID is the canonical hash of every field."""

    allocation_id: str
    created_at: str
    source_archive_sha256: str
    semantic_commit: str
    model_id: str
    model_sha256: str
    tokenizer_sha256: str
    dataset_sha256: str
    config_sha256: str
    gpu_uuid: str
    gpu_hours: float
    artifact_root: str
    candidate_ids: tuple[str, ...]
    evidence_class: EvidenceClass = EvidenceClass.ADMISSION

    @classmethod
    def from_object(cls, value: object) -> ExperimentPlan:
        if not isinstance(value, dict):
            raise ExperimentContractError("plan must be a JSON object")
        expected = {
            "schema",
            "schema_version",
            "allocation_id",
            "created_at",
            "source_archive_sha256",
            "semantic_commit",
            "model_id",
            "model_sha256",
            "tokenizer_sha256",
            "dataset_sha256",
            "config_sha256",
            "gpu_uuid",
            "gpu_hours",
            "artifact_root",
            "candidate_ids",
            "evidence_class",
        }
        if set(value) != expected:
            raise ExperimentContractError(
                f"plan fields differ: missing={sorted(expected - set(value))}, "
                f"unknown={sorted(set(value) - expected)}"
            )
        if value["schema"] != "ttt.experiment_plan" or value["schema_version"] != 1:
            raise ExperimentContractError("unsupported experiment plan schema/version")
        raw_candidates = value["candidate_ids"]
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ExperimentContractError("candidate_ids must be a non-empty array")
        candidate_ids = tuple(
            _text(candidate, field="candidate_id") for candidate in raw_candidates
        )
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ExperimentContractError("candidate_ids must be unique")
        try:
            evidence_class = EvidenceClass(
                _text(value["evidence_class"], field="evidence_class")
            )
        except ValueError as exc:
            raise ExperimentContractError("unsupported evidence_class") from exc
        if evidence_class is EvidenceClass.CPU_DIAGNOSTIC:
            raise ExperimentContractError(
                "cpu-diagnostic is an artifact class, not an experiment plan class"
            )
        return cls(
            allocation_id=_text(value["allocation_id"], field="allocation_id"),
            created_at=_text(value["created_at"], field="created_at"),
            source_archive_sha256=_sha256(
                value["source_archive_sha256"], field="source_archive_sha256"
            ),
            semantic_commit=_git_sha(value["semantic_commit"]),
            model_id=_text(value["model_id"], field="model_id"),
            model_sha256=_sha256(value["model_sha256"], field="model_sha256"),
            tokenizer_sha256=_sha256(
                value["tokenizer_sha256"], field="tokenizer_sha256"
            ),
            dataset_sha256=_sha256(value["dataset_sha256"], field="dataset_sha256"),
            config_sha256=_sha256(value["config_sha256"], field="config_sha256"),
            gpu_uuid=_gpu_uuid(value["gpu_uuid"]),
            gpu_hours=_positive_float(value["gpu_hours"], field="gpu_hours"),
            artifact_root=_text(value["artifact_root"], field="artifact_root"),
            candidate_ids=candidate_ids,
            evidence_class=evidence_class,
        )

    @classmethod
    def from_json(cls, path: str | Path) -> ExperimentPlan:
        try:
            value: object = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperimentContractError(
                f"cannot read experiment plan: {exc}"
            ) from exc
        return cls.from_object(value)

    def to_object(self) -> JsonObject:
        candidates: list[JsonValue] = list(self.candidate_ids)
        return {
            "schema": "ttt.experiment_plan",
            "schema_version": 1,
            "allocation_id": self.allocation_id,
            "created_at": self.created_at,
            "source_archive_sha256": self.source_archive_sha256,
            "semantic_commit": self.semantic_commit,
            "model_id": self.model_id,
            "model_sha256": self.model_sha256,
            "tokenizer_sha256": self.tokenizer_sha256,
            "dataset_sha256": self.dataset_sha256,
            "config_sha256": self.config_sha256,
            "gpu_uuid": self.gpu_uuid,
            "gpu_hours": self.gpu_hours,
            "artifact_root": self.artifact_root,
            "candidate_ids": candidates,
            "evidence_class": self.evidence_class.value,
        }

    @property
    def experiment_id(self) -> str:
        return f"ttt-exp-{content_hash(self.to_object())[:24]}"

    def stage_id(self, stage: str, inputs: JsonObject | None = None) -> str:
        return (
            "ttt-stage-"
            + content_hash(
                {
                    "experiment_id": self.experiment_id,
                    "stage": _text(stage, field="stage"),
                    "inputs": cast(JsonObject, inputs or {}),
                }
            )[:24]
        )

    def attempt_id(
        self,
        stage: str,
        *,
        ordinal: int,
        launch_nonce: str,
        inputs: JsonObject | None = None,
    ) -> str:
        if type(ordinal) is not int or ordinal < 1:
            raise ExperimentContractError("attempt ordinal must be a positive integer")
        nonce = _text(launch_nonce, field="launch_nonce")
        return (
            "ttt-attempt-"
            + content_hash(
                {
                    "stage_id": self.stage_id(stage, inputs),
                    "ordinal": ordinal,
                    "launch_nonce": nonce,
                }
            )[:24]
        )


@dataclass(frozen=True, slots=True)
class VerifiedEvent:
    """External fact accepted by the pure transition engine."""

    event_id: str
    kind: EventKind
    timestamp: str
    payload: JsonObject

    def to_object(self) -> JsonObject:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    @classmethod
    def from_object(cls, value: object) -> VerifiedEvent:
        if not isinstance(value, dict) or set(value) != {
            "event_id",
            "kind",
            "timestamp",
            "payload",
        }:
            raise ExperimentContractError("event has invalid fields")
        try:
            kind = EventKind(_text(value["kind"], field="kind"))
        except ValueError as exc:
            raise ExperimentContractError("unsupported event kind") from exc
        payload = value["payload"]
        if not isinstance(payload, dict):
            raise ExperimentContractError("event payload must be an object")
        return cls(
            event_id=_text(value["event_id"], field="event_id"),
            kind=kind,
            timestamp=_text(value["timestamp"], field="timestamp"),
            payload=cast(JsonObject, payload),
        )


@dataclass(frozen=True, slots=True)
class HumanReview:
    """Supplied review record. Test fixtures remain distinguishable from real review."""

    reviewer_id: str
    submitted_at: str
    packet_id: str
    candidate_id: str
    humour: int
    surprise: int
    distinctiveness: int
    test_fixture: bool = False

    @classmethod
    def from_object(cls, value: object) -> HumanReview:
        if not isinstance(value, dict):
            raise ExperimentContractError("review must be a JSON object")
        expected = {
            "reviewer_id",
            "submitted_at",
            "packet_id",
            "candidate_id",
            "humour",
            "surprise",
            "distinctiveness",
            "test_fixture",
        }
        if set(value) != expected:
            raise ExperimentContractError("review has invalid fields")

        def rating(name: str) -> int:
            raw = value[name]
            if type(raw) is not int or not 1 <= raw <= 5:
                raise ExperimentContractError(f"{name} must be an integer from 1 to 5")
            return raw

        if type(value["test_fixture"]) is not bool:
            raise ExperimentContractError("test_fixture must be boolean")
        return cls(
            reviewer_id=_text(value["reviewer_id"], field="reviewer_id"),
            submitted_at=_text(value["submitted_at"], field="submitted_at"),
            packet_id=_text(value["packet_id"], field="packet_id"),
            candidate_id=_text(value["candidate_id"], field="candidate_id"),
            humour=rating("humour"),
            surprise=rating("surprise"),
            distinctiveness=rating("distinctiveness"),
            test_fixture=value["test_fixture"],
        )

    def to_object(self) -> JsonObject:
        return {
            "reviewer_id": self.reviewer_id,
            "submitted_at": self.submitted_at,
            "packet_id": self.packet_id,
            "candidate_id": self.candidate_id,
            "humour": self.humour,
            "surprise": self.surprise,
            "distinctiveness": self.distinctiveness,
            "test_fixture": self.test_fixture,
        }
