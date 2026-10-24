"""Creative Teacher persona mutation, adapters, and validation."""

from .adapters import (
    ApiTeacherStub,
    LocalModelTeacherStub,
    ReplayCandidateSpec,
    ReplayTeacherAdapter,
    SyntheticTeacherAdapter,
    TeacherAdapter,
    TeacherFixtureMissingError,
    TeacherUnavailableError,
)
from .model import (
    TeacherBatch,
    TeacherCandidate,
    TeacherProvenance,
    TeacherRequest,
    TeacherTask,
)
from .persona import PersonaDimension, mutate_persona
from .validation import (
    CandidateValidation,
    ForbiddenDisclosureValidator,
    OperationalStatus,
    OperationalValidator,
    StyleValidator,
    TaskShapeValidator,
    ValidatedTeacherBatch,
    ValidationDecision,
    validate_teacher_batch,
)

__all__ = [
    "ApiTeacherStub",
    "CandidateValidation",
    "ForbiddenDisclosureValidator",
    "LocalModelTeacherStub",
    "OperationalStatus",
    "OperationalValidator",
    "PersonaDimension",
    "ReplayCandidateSpec",
    "ReplayTeacherAdapter",
    "StyleValidator",
    "SyntheticTeacherAdapter",
    "TaskShapeValidator",
    "TeacherAdapter",
    "TeacherBatch",
    "TeacherCandidate",
    "TeacherFixtureMissingError",
    "TeacherProvenance",
    "TeacherRequest",
    "TeacherTask",
    "TeacherUnavailableError",
    "ValidatedTeacherBatch",
    "ValidationDecision",
    "mutate_persona",
    "validate_teacher_batch",
]
