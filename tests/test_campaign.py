"""CPU-only admission, corpus and budget control tests; no model downloads."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from techrotic_training_triumvirate.evaluation import (
    EvaluationContext,
    load_benchmark_v1,
)
from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    InterpreterResult,
    canonical_json,
)
from techrotic_training_triumvirate.session import (
    DeterministicRenderer,
    SessionRecording,
)
from techrotic_training_triumvirate.training.campaign import (
    CampaignError,
    evaluation_source,
    parse_model_action,
    prepare_pilot_corpus,
    run_pilot_campaign,
    verify_completed_worker,
)
from techrotic_training_triumvirate.training.data import load_corpus_examples
from techrotic_training_triumvirate.training.pilot import build_pilot_plan

TEST_GPU_UUID = "GPU-22222222-2222-2222-2222-222222222222"


def test_real_pilot_corpus_replays_and_has_no_reserved_benchmark_worlds(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    identity = prepare_pilot_corpus(
        corpus, episodes_per_tier=3, turns=5, git_commit="test"
    )
    repeated = prepare_pilot_corpus(
        corpus, episodes_per_tier=3, turns=5, git_commit="test"
    )
    assert identity == repeated
    sources, loaded = load_corpus_examples(corpus)
    assert loaded.to_object() == identity
    assert {s.tier for s in sources} == {"T1", "T2", "T3"}
    assert any(s.mode == "recovery" for s in sources if s.tier == "T3")
    assert all(s.split != "frozen_eval" for s in sources)
    assert "interpreter_result" not in canonical_json([s.target for s in sources])
    plan = build_pilot_plan(corpus)
    assert plan["benchmark_clean"] is True


def test_different_existing_corpus_is_refused(tmp_path: Path) -> None:
    prepare_pilot_corpus(tmp_path, episodes_per_tier=2, turns=4)
    with pytest.raises(CampaignError, match="differs"):
        prepare_pilot_corpus(tmp_path, episodes_per_tier=3, turns=4)


def test_malformed_generation_becomes_authoritatively_rejected_command() -> None:
    action = parse_model_action("not JSON", command_id="parse-1")
    assert action.commands[0].body == {"op": "invalid_model_output"}
    assert action.commands[0].command_id == "parse-1"
    empty = parse_model_action('{"commands":[],"communications":[]}', command_id="p2")
    assert not empty.commands


def test_evaluation_input_keeps_delayed_feedback_and_prelude_rejection() -> None:
    recording = SessionRecording.new(session_id="test", run_id="test", seed=750000)
    observation = recording.initial_observation
    renderer = DeterministicRenderer()
    event = AuthoritativeEvent(
        event_id="delayed-failure",
        kind="execution-failed",
        tick=3,
        related_command_ids=("older-command",),
        data={"code": "ROUTE_BLOCKED"},
    )
    context = EvaluationContext(
        case_id="test",
        turn_index=3,
        observation_generation=7,
        observation=observation,
        structured_observation=renderer.structured_observation(observation),
        compact_observation=renderer.compact_observation(observation),
        previous_results=(),
        recent_events=(event,),
        persona=load_benchmark_v1().persona,
    )
    source = evaluation_source(context, None)
    assert source.mode == "recovery"
    assert source.input["world_events"] == [event.to_dict()]
    assert source.input["observation_generation"] == 7
    assert "prior_failure" not in source.input
    rejection = InterpreterResult(
        command_id="prelude", accepted=False, code="ENTITY_UNKNOWN", detail={}
    )
    source = evaluation_source(replace(context, previous_results=(rejection,)), None)
    assert source.input["interpreter_results"] == [rejection.to_dict()]
    assert "prior_failure" not in source.input


def test_campaign_budget_and_opt_in_refuse_before_execution(tmp_path: Path) -> None:
    with pytest.raises(CampaignError, match="allow_heavy"):
        run_pilot_campaign(
            tmp_path, tmp_path, execution_host="h", allocation_id="a", git_commit="r"
        )
    with pytest.raises(CampaignError, match="finite"):
        run_pilot_campaign(
            tmp_path,
            tmp_path,
            execution_host="h",
            allocation_id="a",
            git_commit="r",
            allow_heavy=True,
            gpu_hours=float("nan"),
            gpu_uuid=TEST_GPU_UUID,
        )


def test_worker_failure_is_preserved_and_identity_changes_cannot_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus"
    prepare_pilot_corpus(corpus, episodes_per_tier=2, turns=4)
    monkeypatch.setattr(
        "techrotic_training_triumvirate.training.campaign.collect_host",
        lambda: {"hostname": "test"},
    )
    calls: list[list[str]] = []

    def failed(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["timeout"] == 72
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        assert environment["CUDA_VISIBLE_DEVICES"] == TEST_GPU_UUID
        assert environment["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
        return subprocess.CompletedProcess(command, 9)

    monkeypatch.setattr(
        "techrotic_training_triumvirate.training.campaign.subprocess.run", failed
    )
    output = tmp_path / "run"
    result = run_pilot_campaign(
        corpus,
        output,
        execution_host="h",
        allocation_id="a",
        git_commit="r",
        allow_heavy=True,
        gpu_hours=0.1,
        gpu_uuid=TEST_GPU_UUID,
    )
    assert len(calls) == 5
    assert result["status"] == "incomplete"
    assert result["substantive_campaign_executed"] is False
    record = json.loads((output / "campaign.json").read_text())
    assert record["gpu_selection"]["uuid"] == TEST_GPU_UUID
    assert record["variants"]["operational"]["returncode"] == 9
    with pytest.raises(CampaignError, match="identity changed"):
        run_pilot_campaign(
            corpus,
            output,
            execution_host="h",
            allocation_id="changed",
            git_commit="r",
            allow_heavy=True,
            gpu_hours=0.1,
            gpu_uuid=TEST_GPU_UUID,
        )


def test_completed_worker_without_hash_bound_reports_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CampaignError, match="missing or invalid"):
        verify_completed_worker(tmp_path, variant="joint", git_commit="test")
    (tmp_path / "worker-result.json").write_text(
        '{"variant":"joint","quality_evidence":true}', encoding="utf-8"
    )
    with pytest.raises(CampaignError, match="missing or invalid"):
        verify_completed_worker(tmp_path, variant="joint", git_commit="test")


def test_campaign_refuses_implicit_or_numeric_gpu_selection(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    prepare_pilot_corpus(corpus, episodes_per_tier=2, turns=4)
    for selection in (None, "0"):
        with pytest.raises(ValueError, match="UUID"):
            run_pilot_campaign(
                corpus,
                tmp_path / "run",
                execution_host="h",
                allocation_id="a",
                git_commit="r",
                allow_heavy=True,
                gpu_hours=0.1,
                gpu_uuid=selection,
            )
