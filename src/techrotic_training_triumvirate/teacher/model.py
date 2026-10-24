"""Model-agnostic Creative Teacher request/candidate/provenance records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    PersonaSpec,
    SourceProvenance,
    canonical_json,
    content_hash,
)


class TeacherTask(str, Enum):
    EVENT_REACTION = "event_reaction"
    PERSONA_REWRITE = "persona_rewrite"
    CODEWORD_DOCTRINE = "codeword_doctrine"
    TACTICAL_CANDIDATE = "tactical_candidate"
    PERSONA_INVENTION = "persona_invention"
    PERSONA_MUTATION = "persona_mutation"


def clone_json_object(value: JsonObject) -> JsonObject:
    cloned = json.loads(canonical_json(value))
    if not isinstance(cloned, dict):
        raise AssertionError("canonical JSON object clone must remain an object")
    return cloned


@dataclass(frozen=True, slots=True)
class TeacherRequest:
    request_id: str
    task: TeacherTask
    persona: PersonaSpec | None
    input_text: str | None
    authoritative_context: JsonObject
    forbidden_disclosures: tuple[str, ...]
    candidate_count: int
    seed: int

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")
        if not 1 <= self.candidate_count <= 32:
            raise ValueError("candidate_count must be between 1 and 32")
        if any(not item for item in self.forbidden_disclosures):
            raise ValueError("forbidden disclosures must not contain empty strings")
        object.__setattr__(
            self,
            "authoritative_context",
            clone_json_object(self.authoritative_context),
        )

    def context_copy(self) -> JsonObject:
        return clone_json_object(self.authoritative_context)


@dataclass(frozen=True, slots=True)
class TeacherProvenance:
    adapter_id: str
    model_ref: str
    template_version: str
    settings: JsonObject
    request_id: str
    candidate_index: int
    seed: int

    def __post_init__(self) -> None:
        if self.candidate_index < 0:
            raise ValueError("candidate_index must be non-negative")
        for field_name, value in (
            ("adapter_id", self.adapter_id),
            ("model_ref", self.model_ref),
            ("template_version", self.template_version),
            ("request_id", self.request_id),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        object.__setattr__(self, "settings", clone_json_object(self.settings))


@dataclass(frozen=True, slots=True)
class TeacherCandidate:
    candidate_id: str
    task: TeacherTask
    text: str | None
    payload: JsonObject
    provenance: TeacherProvenance

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id must not be empty")
        if self.text is None and not self.payload:
            raise ValueError("candidate must contain text or payload")
        if self.text is not None and not self.text.strip():
            raise ValueError("candidate text must be null or non-empty")
        object.__setattr__(self, "payload", clone_json_object(self.payload))

    def content_hash(self) -> str:
        return content_hash(
            {
                "task": self.task.value,
                "text": self.text,
                "payload": self.payload,
            }
        )

    def source_provenance(self) -> SourceProvenance:
        return SourceProvenance(
            source_id=self.candidate_id,
            source_class="teacher-output",
            uri=None,
            revision=self.provenance.model_ref,
            license_id=None,
            source_content_hash=self.content_hash(),
            metadata={
                "adapter_id": self.provenance.adapter_id,
                "template_version": self.provenance.template_version,
                "settings": self.provenance.settings,
                "request_id": self.provenance.request_id,
                "candidate_index": self.provenance.candidate_index,
                "seed": self.provenance.seed,
            },
        )


@dataclass(frozen=True, slots=True)
class TeacherBatch:
    request_id: str
    candidates: tuple[TeacherCandidate, ...]

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must not be empty")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        if any(
            candidate.provenance.request_id != self.request_id
            for candidate in self.candidates
        ):
            raise ValueError("candidate provenance request IDs must match batch")
