from __future__ import annotations

import json

import pytest

from techrotic_training_triumvirate.schemas.fixtures import t0_persona
from techrotic_training_triumvirate.teacher import (
    ApiTeacherStub,
    LocalModelTeacherStub,
    ReplayCandidateSpec,
    ReplayTeacherAdapter,
    SyntheticTeacherAdapter,
    TeacherFixtureMissingError,
    TeacherRequest,
    TeacherTask,
    TeacherUnavailableError,
)


def request(
    *,
    task: TeacherTask = TeacherTask.EVENT_REACTION,
    candidate_count: int = 3,
    input_text: str | None = "enemy crossed the bridge",
    forbidden: tuple[str, ...] = (),
) -> TeacherRequest:
    return TeacherRequest(
        request_id=f"request-{task.value}",
        task=task,
        persona=t0_persona(),
        input_text=input_text,
        authoritative_context={
            "visible_event": "bridge contact",
            "objective": "hold east",
        },
        forbidden_disclosures=forbidden,
        candidate_count=candidate_count,
        seed=24301,
    )


def test_replay_adapter_is_exact_and_provenance_bound() -> None:
    req = request(candidate_count=2)
    adapter = ReplayTeacherAdapter(
        {
            req.request_id: (
                ReplayCandidateSpec(req.task, "first reaction", {}),
                ReplayCandidateSpec(req.task, "second reaction", {}),
            )
        }
    )

    first = adapter.generate(req)
    second = adapter.generate(req)

    assert first == second
    assert [c.text for c in first.candidates] == [
        "first reaction",
        "second reaction",
    ]
    assert [c.provenance.candidate_index for c in first.candidates] == [0, 1]
    assert all(c.provenance.adapter_id == "replay-fixture" for c in first.candidates)
    assert all(c.provenance.request_id == req.request_id for c in first.candidates)


def test_replay_adapter_refuses_missing_or_mismatched_fixture() -> None:
    req = request(candidate_count=2)
    adapter = ReplayTeacherAdapter({})

    with pytest.raises(TeacherFixtureMissingError):
        adapter.generate(req)


@pytest.mark.parametrize("task", list(TeacherTask))
def test_synthetic_adapter_supports_every_teacher_task(task: TeacherTask) -> None:
    req = request(task=task, candidate_count=2)
    adapter = SyntheticTeacherAdapter()

    batch = adapter.generate(req)

    assert len(batch.candidates) == 2
    assert [candidate.candidate_id for candidate in batch.candidates] == [
        f"{req.request_id}:c0",
        f"{req.request_id}:c1",
    ]
    assert all(candidate.task is task for candidate in batch.candidates)
    assert all(candidate.provenance.model_ref.startswith("synthetic://") for candidate in batch.candidates)


def test_synthetic_adapter_is_deterministic_and_preserves_multiple_candidates() -> None:
    req = request(candidate_count=5)
    adapter = SyntheticTeacherAdapter()

    first = adapter.generate(req)
    second = adapter.generate(req)

    assert first == second
    assert len(first.candidates) == 5
    assert len({candidate.candidate_id for candidate in first.candidates}) == 5
    assert [c.provenance.candidate_index for c in first.candidates] == list(range(5))


def test_synthetic_teacher_redacts_forbidden_disclosure() -> None:
    secret = "reactor-core-is-dead"
    req = request(
        candidate_count=4,
        input_text=f"Do not say that {secret}; react to contact.",
        forbidden=(secret,),
    )

    batch = SyntheticTeacherAdapter().generate(req)
    rendered = json.dumps(
        [
            {"text": candidate.text, "payload": candidate.payload}
            for candidate in batch.candidates
        ],
        sort_keys=True,
    )

    assert secret not in rendered
    assert "[REDACTED]" in rendered


def test_teacher_request_context_is_a_copy_not_world_authority_state() -> None:
    world_projection = {"status": "contested", "nested": {"route": "north"}}
    req = TeacherRequest(
        request_id="request-copy",
        task=TeacherTask.TACTICAL_CANDIDATE,
        persona=t0_persona(),
        input_text="propose a manoeuvre",
        authoritative_context=world_projection,
        forbidden_disclosures=(),
        candidate_count=1,
        seed=1,
    )

    req.authoritative_context["status"] = "teacher-mutated-copy"

    assert world_projection["status"] == "contested"


def test_candidate_provenance_can_be_promoted_to_source_record() -> None:
    candidate = SyntheticTeacherAdapter().generate(request(candidate_count=1)).candidates[0]

    provenance = candidate.source_provenance()

    assert provenance.source_class == "teacher-output"
    assert provenance.source_content_hash == candidate.content_hash()
    assert provenance.metadata["adapter_id"] == "synthetic-teacher"


@pytest.mark.parametrize(
    "adapter",
    [
        LocalModelTeacherStub("unselected://local"),
        ApiTeacherStub("unselected://api"),
    ],
)
def test_external_backend_stubs_have_no_live_dependency(adapter: object) -> None:
    with pytest.raises(TeacherUnavailableError):
        adapter.generate(request(candidate_count=1))  # type: ignore[attr-defined]
