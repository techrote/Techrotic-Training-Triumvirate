"""Creative Teacher adapter interfaces and deterministic CI implementations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from techrotic_training_triumvirate.determinism import seeded_rng
from techrotic_training_triumvirate.schemas import JsonObject, content_hash

from .model import (
    TeacherBatch,
    TeacherCandidate,
    TeacherProvenance,
    TeacherRequest,
    TeacherTask,
    clone_json_object,
)


class TeacherAdapter(Protocol):
    @property
    def adapter_id(self) -> str: ...

    @property
    def model_ref(self) -> str: ...

    def generate(self, request: TeacherRequest) -> TeacherBatch: ...


class TeacherUnavailableError(RuntimeError):
    """Raised when an intentionally unconfigured adapter is invoked."""


class TeacherFixtureMissingError(KeyError):
    """Raised when replay input is absent or incompatible."""


@dataclass(frozen=True, slots=True)
class ReplayCandidateSpec:
    task: TeacherTask
    text: str | None
    payload: JsonObject


class ReplayTeacherAdapter:
    """Replay exact recorded candidate specifications without model access."""

    def __init__(
        self,
        fixtures: Mapping[str, tuple[ReplayCandidateSpec, ...]],
        *,
        adapter_id: str = "replay-fixture",
        model_ref: str = "fixture://recorded",
        template_version: str = "replay-v1",
    ) -> None:
        self._fixtures = dict(fixtures)
        self._adapter_id = adapter_id
        self._model_ref = model_ref
        self._template_version = template_version

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def model_ref(self) -> str:
        return self._model_ref

    def generate(self, request: TeacherRequest) -> TeacherBatch:
        specs = self._fixtures.get(request.request_id)
        if specs is None:
            raise TeacherFixtureMissingError(request.request_id)
        if len(specs) != request.candidate_count:
            raise TeacherFixtureMissingError(
                f"{request.request_id}: expected {request.candidate_count} "
                f"candidates, fixture has {len(specs)}"
            )
        candidates = []
        for index, spec in enumerate(specs):
            if spec.task is not request.task:
                raise TeacherFixtureMissingError(
                    f"{request.request_id}: task mismatch at candidate {index}"
                )
            candidates.append(
                TeacherCandidate(
                    candidate_id=f"{request.request_id}:c{index}",
                    task=spec.task,
                    text=spec.text,
                    payload=clone_json_object(spec.payload),
                    provenance=TeacherProvenance(
                        adapter_id=self.adapter_id,
                        model_ref=self.model_ref,
                        template_version=self._template_version,
                        settings={"mode": "replay"},
                        request_id=request.request_id,
                        candidate_index=index,
                        seed=request.seed,
                    ),
                )
            )
        return TeacherBatch(request.request_id, tuple(candidates))


def _redact(text: str, forbidden: tuple[str, ...]) -> str:
    result = text
    for secret in sorted(forbidden, key=len, reverse=True):
        result = result.replace(secret, "[REDACTED]")
    return result


class SyntheticTeacherAdapter:
    """Small deterministic generator for tests and pipeline development."""

    _VOICES = (
        "copper-riddle",
        "crooked-logic",
        "ritual-static",
        "impatient-gears",
        "paranoid-sprocket",
        "triumphant-scrap",
    )
    _CODEWORDS = ("locust", "hinge", "crown", "anvil", "moth", "cinder")

    def __init__(
        self,
        *,
        adapter_id: str = "synthetic-teacher",
        model_ref: str = "synthetic://deterministic-v1",
        template_version: str = "synthetic-v1",
    ) -> None:
        self._adapter_id = adapter_id
        self._model_ref = model_ref
        self._template_version = template_version

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def model_ref(self) -> str:
        return self._model_ref

    def _candidate(
        self,
        request: TeacherRequest,
        index: int,
    ) -> TeacherCandidate:
        rng = seeded_rng(request.seed + index * 104729)
        voice = self._VOICES[rng.randrange(len(self._VOICES))]
        codeword = self._CODEWORDS[rng.randrange(len(self._CODEWORDS))]
        source = _redact(request.input_text or "", request.forbidden_disclosures)
        archetype = (
            request.persona.archetype
            if request.persona is not None
            else "unassigned-character"
        )
        context_digest = content_hash(request.context_copy())[:12]

        text: str | None = None
        payload: JsonObject = {}
        if request.task is TeacherTask.EVENT_REACTION:
            text = f"{archetype}/{voice}: react to {source or 'the event'}."
        elif request.task is TeacherTask.PERSONA_REWRITE:
            text = f"{archetype}/{voice}: {source or 'say nothing'}"
        elif request.task is TeacherTask.CODEWORD_DOCTRINE:
            payload = {
                "codeword": f"{codeword}-{index + 1}",
                "meaning": source or "unspecified manoeuvre",
            }
        elif request.task is TeacherTask.TACTICAL_CANDIDATE:
            payload = {
                "proposal": source or "probe the contested objective",
                "doctrine_voice": voice,
                "context_digest": context_digest,
            }
        elif request.task is TeacherTask.PERSONA_INVENTION:
            payload = {
                "archetype_seed": f"{voice}-{archetype}",
                "temperament": self._VOICES[rng.randrange(len(self._VOICES))],
                "codeword_seed": codeword,
            }
        elif request.task is TeacherTask.PERSONA_MUTATION:
            payload = {
                "dimension": "temperament",
                "value": voice,
                "source_persona_id": (
                    request.persona.persona_id if request.persona is not None else None
                ),
            }
        else:
            raise AssertionError(f"unhandled teacher task: {request.task}")

        return TeacherCandidate(
            candidate_id=f"{request.request_id}:c{index}",
            task=request.task,
            text=text,
            payload=payload,
            provenance=TeacherProvenance(
                adapter_id=self.adapter_id,
                model_ref=self.model_ref,
                template_version=self._template_version,
                settings={
                    "mode": "deterministic-synthetic",
                    "voice": voice,
                    "context_digest": context_digest,
                },
                request_id=request.request_id,
                candidate_index=index,
                seed=request.seed,
            ),
        )

    def generate(self, request: TeacherRequest) -> TeacherBatch:
        return TeacherBatch(
            request.request_id,
            tuple(
                self._candidate(request, index)
                for index in range(request.candidate_count)
            ),
        )


class LocalModelTeacherStub:
    """Dependency-free placeholder for a later admitted local model backend."""

    def __init__(self, model_ref: str) -> None:
        self._model_ref = model_ref

    @property
    def adapter_id(self) -> str:
        return "local-model-stub"

    @property
    def model_ref(self) -> str:
        return self._model_ref

    def generate(self, request: TeacherRequest) -> TeacherBatch:
        del request
        raise TeacherUnavailableError(
            "local model adapter is not configured; use an explicitly admitted runtime integration"
        )


class ApiTeacherStub:
    """Dependency-free placeholder for a later admitted external API backend."""

    def __init__(self, model_ref: str) -> None:
        self._model_ref = model_ref

    @property
    def adapter_id(self) -> str:
        return "api-teacher-stub"

    @property
    def model_ref(self) -> str:
        return self._model_ref

    def generate(self, request: TeacherRequest) -> TeacherBatch:
        del request
        raise TeacherUnavailableError(
            "API teacher adapter is not configured or admitted"
        )
