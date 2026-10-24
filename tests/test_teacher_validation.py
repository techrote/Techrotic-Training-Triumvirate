from __future__ import annotations

import pytest

from techrotic_training_triumvirate.schemas.fixtures import t0_persona
from techrotic_training_triumvirate.teacher import (
    ForbiddenDisclosureValidator,
    OperationalStatus,
    SyntheticTeacherAdapter,
    TeacherCandidate,
    TeacherProvenance,
    TeacherRequest,
    TeacherTask,
    ValidationDecision,
    validate_teacher_batch,
)


class AcceptOperational:
    def validate(
        self,
        candidate: TeacherCandidate,
        request: TeacherRequest,
    ) -> ValidationDecision:
        del candidate, request
        return ValidationDecision(True)


class RejectOperational:
    def validate(
        self,
        candidate: TeacherCandidate,
        request: TeacherRequest,
    ) -> ValidationDecision:
        del candidate, request
        return ValidationDecision(False, ("not admitted by World Authority",))


def request(*, secret: str = "classified-value") -> TeacherRequest:
    return TeacherRequest(
        request_id="request-validation",
        task=TeacherTask.EVENT_REACTION,
        persona=t0_persona(),
        input_text="react to contact",
        authoritative_context={"event": "contact"},
        forbidden_disclosures=(secret,),
        candidate_count=1,
        seed=4,
    )


def test_operational_truth_defaults_to_unvalidated() -> None:
    req = request()
    batch = SyntheticTeacherAdapter().generate(req)

    validated = validate_teacher_batch(batch, req)

    result = validated.validations[0]
    assert result.style_accepted is True
    assert result.operational_status is OperationalStatus.UNVALIDATED
    assert result.operational_reasons == ()


def test_style_and_operational_validation_are_independent() -> None:
    req = request()
    batch = SyntheticTeacherAdapter().generate(req)

    accepted = validate_teacher_batch(
        batch,
        req,
        operational_validators=(AcceptOperational(),),
    )
    rejected = validate_teacher_batch(
        batch,
        req,
        operational_validators=(RejectOperational(),),
    )

    assert accepted.validations[0].style_accepted is True
    assert accepted.validations[0].operational_status is OperationalStatus.ACCEPTED
    assert rejected.validations[0].style_accepted is True
    assert rejected.validations[0].operational_status is OperationalStatus.REJECTED


def test_forbidden_disclosure_validator_rejects_teacher_output() -> None:
    secret = "classified-value"
    req = request(secret=secret)
    provenance = TeacherProvenance(
        adapter_id="bad-fixture",
        model_ref="fixture://bad",
        template_version="1",
        settings={},
        request_id=req.request_id,
        candidate_index=0,
        seed=req.seed,
    )
    candidate = TeacherCandidate(
        candidate_id="bad:c0",
        task=req.task,
        text=f"I reveal {secret}",
        payload={},
        provenance=provenance,
    )
    batch = type(SyntheticTeacherAdapter().generate(req))(
        req.request_id,
        (candidate,),
    )

    validated = validate_teacher_batch(
        batch,
        req,
        style_validators=(ForbiddenDisclosureValidator(),),
    )

    assert validated.validations[0].style_accepted is False
    assert "forbidden disclosure" in validated.validations[0].style_reasons[0]


def test_malformed_empty_candidate_is_rejected_at_construction() -> None:
    provenance = TeacherProvenance(
        adapter_id="fixture",
        model_ref="fixture://empty",
        template_version="1",
        settings={},
        request_id="request-empty",
        candidate_index=0,
        seed=0,
    )

    with pytest.raises(ValueError, match="text or payload"):
        TeacherCandidate(
            candidate_id="empty",
            task=TeacherTask.EVENT_REACTION,
            text=None,
            payload={},
            provenance=provenance,
        )
