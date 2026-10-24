from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from techrotic_training_triumvirate.corpus import (
    CorpusConfig,
    CorpusSource,
    CorpusSplit,
    CorpusTier,
    TeacherEnrichment,
    assemble_corpus,
    write_corpus,
)
from techrotic_training_triumvirate.schemas import (
    SourceProvenance,
    canonical_json,
)
from techrotic_training_triumvirate.schemas.fixtures import (
    PRIVATE_SENTINEL,
    t0_episode,
    t0_source_provenance,
)


def _source(
    *,
    tier: CorpusTier = CorpusTier.T0,
    provenance: tuple[SourceProvenance, ...] | None = None,
    enrichments: tuple[TeacherEnrichment, ...] = (),
) -> CorpusSource:
    return CorpusSource(
        episode=t0_episode(),
        tier=tier,
        provenance=provenance or (t0_source_provenance(),),
        teacher_enrichments=enrichments,
    )


def _teacher_provenance(*, admitted: bool) -> SourceProvenance:
    return SourceProvenance(
        source_id="teacher-fixture",
        source_class="teacher-output",
        uri="fixture://teacher",
        revision="teacher-v1",
        license_id="fixture-license" if admitted else None,
        source_content_hash="a" * 64,
        metadata={"license_disposition": "admitted"} if admitted else {},
    )


def _teacher_enrichment(
    *,
    operational_facts: dict[str, object] | None = None,
) -> TeacherEnrichment:
    facts = operational_facts or {"relay_status": "contested"}
    return TeacherEnrichment(
        source_id="teacher-fixture",
        turn_id=0,
        operational_facts=facts,  # type: ignore[arg-type]
        style_text="The relay squeals like a stripped gear.",
    )


def _quarantine_codes(build: object) -> set[str]:
    result = build
    assert hasattr(result, "quarantine")
    return {
        issue.code
        for item in result.quarantine  # type: ignore[union-attr]
        for issue in item.issues
    }


def test_rebuild_is_content_deterministic_and_targets_only_student_emissions() -> None:
    config = CorpusConfig(seed=17, dev_percent=0, shard_size=1)
    first = assemble_corpus((_source(),), config=config)
    second = assemble_corpus((_source(),), config=config)

    assert first.manifest == second.manifest
    assert [(item.name, item.sha256) for item in first.shards] == [
        (item.name, item.sha256) for item in second.shards
    ]
    assert first.examples
    assert all(
        set(example.target) == {"commands", "communications"}
        for example in first.examples
    )
    target_text = canonical_json([example.target for example in first.examples])
    assert "interpreter_result" not in target_text
    assert "world_events" not in target_text
    assert "next_observation" not in target_text


def test_deliberate_secret_leak_is_quarantined() -> None:
    episode = t0_episode()
    hidden_turn = episode.turns[1]
    leaked_communication = replace(
        hidden_turn.assistant_action.communications[0],
        text=f"reactor truth: {PRIVATE_SENTINEL}",
    )
    leaked_action = replace(
        hidden_turn.assistant_action,
        communications=(leaked_communication,),
    )
    leaked_turn = replace(hidden_turn, assistant_action=leaked_action)
    leaked_episode = replace(
        episode,
        turns=(episode.turns[0], leaked_turn, episode.turns[2]),
    )
    source = replace(_source(), episode=leaked_episode)

    build = assemble_corpus((source,), config=CorpusConfig(dev_percent=0))

    assert "SECRET_LEAK" in _quarantine_codes(build)
    assert not build.examples


def test_external_teacher_output_without_license_disposition_is_quarantined() -> None:
    source = _source(
        tier=CorpusTier.T2,
        provenance=(t0_source_provenance(), _teacher_provenance(admitted=False)),
        enrichments=(_teacher_enrichment(),),
    )

    build = assemble_corpus((source,), config=CorpusConfig(dev_percent=0))

    assert "LICENSE_UNADMITTED" in _quarantine_codes(build)


def test_unsupported_teacher_operational_fact_is_quarantined() -> None:
    source = _source(
        tier=CorpusTier.T2,
        provenance=(t0_source_provenance(), _teacher_provenance(admitted=True)),
        enrichments=(
            _teacher_enrichment(
                operational_facts={"relay_status": "already-destroyed"}
            ),
        ),
    )

    build = assemble_corpus((source,), config=CorpusConfig(dev_percent=0))

    assert "UNSUPPORTED_TEACHER_FACT" in _quarantine_codes(build)


def test_exact_and_near_duplicates_do_not_silently_cross_partitions() -> None:
    original = _source()
    exact = _source()
    near = replace(
        _source(),
        episode=replace(t0_episode(), episode_id="episode-t0-near-copy"),
    )

    exact_build = assemble_corpus(
        (original, exact),
        config=CorpusConfig(seed=2, dev_percent=50),
    )
    near_build = assemble_corpus(
        (original, near),
        config=CorpusConfig(seed=2, dev_percent=50),
    )

    assert "DUPLICATE_EPISODE" in _quarantine_codes(exact_build)
    assert "NEAR_DUPLICATE_EPISODE" in _quarantine_codes(near_build)
    assert len({example.split for example in exact_build.examples}) == 1
    assert len({example.split for example in near_build.examples}) == 1


def test_frozen_evaluation_world_cannot_enter_train_or_dev() -> None:
    episode = t0_episode()
    config = CorpusConfig(
        seed=4,
        dev_percent=50,
        frozen_scenario_ids=frozenset({episode.scenario.identity.scenario_id}),
    )

    build = assemble_corpus((_source(),), config=config)

    assert build.examples
    assert {example.split for example in build.examples} == {CorpusSplit.FROZEN_EVAL}
    assert all(example.split is not CorpusSplit.TRAIN for example in build.examples)
    assert all(example.split is not CorpusSplit.DEV for example in build.examples)


def test_ttt009_reserved_family_seed_is_automatically_frozen() -> None:
    episode = t0_episode()
    reserved_identity = replace(
        episode.scenario.identity,
        scenario_id="ttt009-reserved-fixture",
        family="abstract-c2",
        seed=240901,
    )
    reserved_episode = replace(
        episode,
        scenario=replace(episode.scenario, identity=reserved_identity),
    )
    reserved_source = replace(_source(), episode=reserved_episode)

    build = assemble_corpus(
        (reserved_source,),
        config=CorpusConfig(seed=4, dev_percent=0),
    )

    assert build.examples
    assert {example.split for example in build.examples} == {CorpusSplit.FROZEN_EVAL}
    guard = build.manifest["config"]
    assert isinstance(guard, dict)
    guard_identity = guard["frozen_evaluation_guard"]
    assert isinstance(guard_identity, dict)
    assert guard_identity["benchmark_id"] == "ttt-core-frozen"
    assert guard_identity["benchmark_version"] == "1"


def test_ttt009_guard_does_not_freeze_unreserved_seed_from_same_family() -> None:
    episode = t0_episode()
    unreserved_identity = replace(
        episode.scenario.identity,
        scenario_id="ttt009-unreserved-fixture",
        family="abstract-c2",
        seed=240999,
    )
    unreserved_episode = replace(
        episode,
        scenario=replace(episode.scenario, identity=unreserved_identity),
    )
    unreserved_source = replace(_source(), episode=unreserved_episode)

    build = assemble_corpus(
        (unreserved_source,),
        config=CorpusConfig(seed=4, dev_percent=0),
    )

    assert build.examples
    assert {example.split for example in build.examples} == {CorpusSplit.TRAIN}


def test_malformed_recovery_link_is_quarantined() -> None:
    episode = t0_episode()
    turn = episode.turns[1]
    annotations = replace(
        turn.annotations,
        labels={"recovery_of_command_id": "cmd-does-not-exist"},
    )
    malformed = replace(turn, annotations=annotations)
    source = replace(
        _source(),
        episode=replace(
            episode,
            turns=(episode.turns[0], malformed, episode.turns[2]),
        ),
    )

    build = assemble_corpus((source,), config=CorpusConfig(dev_percent=0))

    assert "RECOVERY_MALFORMED" in _quarantine_codes(build)


def test_t3_rejected_action_becomes_recovery_context_not_training_target() -> None:
    episode = t0_episode()
    failed_turn = replace(
        episode.turns[0],
        interpreter_results=(
            replace(
                episode.turns[0].interpreter_results[0],
                accepted=False,
                code="PRECONDITION_FAILED",
                detail={"recoverable": True},
            ),
        ),
        world_events=(),
    )
    recovery_turn = replace(
        episode.turns[1],
        annotations=replace(
            episode.turns[1].annotations,
            labels={"recovery_of_command_id": "cmd-0001"},
        ),
    )
    source = replace(
        _source(tier=CorpusTier.T3),
        episode=replace(
            episode,
            turns=(failed_turn, recovery_turn, episode.turns[2]),
        ),
    )

    build = assemble_corpus((source,), config=CorpusConfig(dev_percent=0))

    assert not build.quarantine
    assert all(example.turn_id != 0 for example in build.examples)
    recovery = next(example for example in build.examples if example.turn_id == 1)
    assert recovery.mode == "recovery"
    assert "prior_failure" in recovery.input
    target_text = canonical_json(recovery.target)
    assert "PRECONDITION_FAILED" not in target_text
    assert "interpreter_results" not in target_text


def test_manifest_reports_composition_teacher_contribution_and_rejections() -> None:
    admitted = _source(
        tier=CorpusTier.T2,
        provenance=(t0_source_provenance(), _teacher_provenance(admitted=True)),
        enrichments=(_teacher_enrichment(),),
    )
    unadmitted = _source(
        tier=CorpusTier.T2,
        provenance=(t0_source_provenance(), _teacher_provenance(admitted=False)),
        enrichments=(_teacher_enrichment(),),
    )

    build = assemble_corpus(
        (admitted, unadmitted),
        config=CorpusConfig(dev_percent=0),
    )

    assert build.manifest["tier_composition"] == {"T2": 2}
    assert build.manifest["world_distribution"] == {"t0-relay": 2}
    assert build.manifest["persona_distribution"] == {"persona-goblin-mechanic-01": 2}
    assert build.manifest["teacher_contribution"] == {
        "examples": 1,
        "source_count": 1,
    }
    rejection_reasons = build.manifest["rejection_reasons"]
    assert isinstance(rejection_reasons, dict)
    assert rejection_reasons["LICENSE_UNADMITTED"] == 1
    assert build.manifest["content_composition"] == {
        "command_count": 2,
        "communication_count": 2,
        "examples_with_commands": 2,
        "examples_with_communications": 2,
        "teacher_enriched_examples": 1,
    }


def test_write_corpus_emits_reproducible_jsonl_and_manifest(tmp_path: Path) -> None:
    build = assemble_corpus(
        (_source(),),
        config=CorpusConfig(seed=9, dev_percent=0, shard_size=1),
    )

    first = tmp_path / "first"
    second = tmp_path / "second"
    write_corpus(build, first)
    write_corpus(build, second)

    first_files = {path.name: path.read_bytes() for path in sorted(first.iterdir())}
    second_files = {path.name: path.read_bytes() for path in sorted(second.iterdir())}
    assert first_files == second_files
    for shard in build.shards:
        assert (first / shard.name).read_text(encoding="utf-8") == shard.content
