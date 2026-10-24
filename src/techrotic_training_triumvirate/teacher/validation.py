"""Separated style and operational validation for teacher candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from techrotic_training_triumvirate.schemas import canonical_json

from .model import TeacherBatch, TeacherCandidate, TeacherRequest, TeacherTask


@dataclass(frozen=True, slots=True)
class ValidationDecision:
    accepted: bool
    reasons: tuple[str, ...] = ()


class StyleValidator(Protocol):
    def validate(
        self,
        candidate: TeacherCandidate,
        request: TeacherRequest,
    ) -> ValidationDecision:
        ...


class OperationalValidator(Protocol):
    def validate(
        self,
        candidate: TeacherCandidate,
        request: TeacherRequest,
    ) -> ValidationDecision:
        ...


class OperationalStatus(str, Enum):
    UNVALIDATED = "unvalidated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CandidateValidation:
    candidate_id: str
    style_accepted: bool
    style_reasons: tuple[str, ...]
    operational_status: OperationalStatus
    operational_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ValidatedTeacherBatch:
    batch: TeacherBatch
    validations: tuple[CandidateValidation, ...]


class TaskShapeValidator:
    """Check that each task returns the expected broad candidate surface."""

    _TEXT_TASKS = {
        TeacherTask.EVENT_REACTION,
        TeacherTask.PERSONA_REWRITE,
    }

    def validate(
        self,
        candidate: TeacherCandidate,
        request: TeacherRequest,
    ) -> ValidationDecision:
        reasons: list[str] = []
        if candidate.task is not request.task:
            reasons.append("candidate task does not match request task")
        if request.task in self._TEXT_TASKS and candidate.text is None:
            reasons.append("task requires text output")
        if request.task not in self._TEXT_TASKS and not candidate.payload:
            reasons.append("task requires structured payload")
        return ValidationDecision(not reasons, tuple(reasons))


class ForbiddenDisclosureValidator:
    """Reject candidate surfaces that contain request-scoped forbidden text."""

    def validate(
        self,
        candidate: TeacherCandidate,
        request: TeacherRequest,
    ) -> ValidationDecision:
        surface = canonical_json(
            {
                "text": candidate.text,
                "payload": candidate.payload,
            }
        )
        disclosed = tuple(
            secret
            for secret in request.forbidden_disclosures
            if secret in surface
        )
        if disclosed:
            return ValidationDecision(
                False,
                tuple(f"forbidden disclosure: {secret}" for secret in disclosed),
            )
        return ValidationDecision(True)


def _run_validators(
    validators: tuple[StyleValidator, ...] | tuple[OperationalValidator, ...],
    candidate: TeacherCandidate,
    request: TeacherRequest,
) -> tuple[bool, tuple[str, ...]]:
    accepted = True
    reasons: list[str] = []
    for validator in validators:
        decision = validator.validate(candidate, request)
        if not decision.accepted:
            accepted = False
        reasons.extend(decision.reasons)
    return accepted, tuple(reasons)


def validate_teacher_batch(
    batch: TeacherBatch,
    request: TeacherRequest,
    *,
    style_validators: tuple[StyleValidator, ...] = (
        TaskShapeValidator(),
        ForbiddenDisclosureValidator(),
    ),
    operational_validators: tuple[OperationalValidator, ...] = (),
) -> ValidatedTeacherBatch:
    """Validate style and operational truth through independent hooks.

    Operational output defaults to UNVALIDATED. Creative candidates therefore
    never become operational truth merely by being well-formed or stylish.
    """
    if batch.request_id != request.request_id:
        raise ValueError("batch request ID does not match request")

    validations = []
    for candidate in batch.candidates:
        style_ok, style_reasons = _run_validators(
            style_validators,
            candidate,
            request,
        )
        if operational_validators:
            operational_ok, operational_reasons = _run_validators(
                operational_validators,
                candidate,
                request,
            )
            operational_status = (
                OperationalStatus.ACCEPTED
                if operational_ok
                else OperationalStatus.REJECTED
            )
        else:
            operational_reasons = ()
            operational_status = OperationalStatus.UNVALIDATED
        validations.append(
            CandidateValidation(
                candidate_id=candidate.candidate_id,
                style_accepted=style_ok,
                style_reasons=style_reasons,
                operational_status=operational_status,
                operational_reasons=operational_reasons,
            )
        )
    return ValidatedTeacherBatch(batch, tuple(validations))
