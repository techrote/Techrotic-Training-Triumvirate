from __future__ import annotations

from techrotic_training_triumvirate.schemas import (
    EpisodeRecord,
    RunManifest,
    ScenarioSpec,
    SourceProvenance,
    TurnRecord,
    content_hash,
    loads_record,
)
from techrotic_training_triumvirate.schemas.fixtures import (
    t0_episode,
    t0_hidden_information_turn,
    t0_normal_turn,
    t0_recovery_turn,
    t0_run_manifest,
    t0_scenario,
    t0_source_provenance,
)


def test_t0_records_round_trip_with_semantic_equality() -> None:
    records = (
        t0_scenario(),
        t0_normal_turn(),
        t0_hidden_information_turn(),
        t0_recovery_turn(),
        t0_episode(),
        t0_source_provenance(),
        t0_run_manifest(),
    )
    expected_types = (
        ScenarioSpec,
        TurnRecord,
        TurnRecord,
        TurnRecord,
        EpisodeRecord,
        SourceProvenance,
        RunManifest,
    )

    for record, expected_type in zip(records, expected_types, strict=True):
        loaded = loads_record(record.to_json(), expected_type=expected_type)
        assert loaded == record
        assert content_hash(loaded) == content_hash(record)


def test_canonical_hash_ignores_mapping_insertion_order() -> None:
    left = t0_normal_turn()
    right = TurnRecord(
        turn_id=left.turn_id,
        observation=type(left.observation)(
            turn_id=left.observation.turn_id,
            world_state_id=left.observation.world_state_id,
            visible_entities=left.observation.visible_entities,
            objective_ids=left.observation.objective_ids,
            event_ids=left.observation.event_ids,
            facts={
                "relay_status": "contested",
                "route_status": {"north": "open"},
            },
        ),
        commander_private_context=left.commander_private_context,
        assistant_action=left.assistant_action,
        interpreter_results=left.interpreter_results,
        world_events=left.world_events,
        next_observation=left.next_observation,
        player_observation=left.player_observation,
        player_intercepts=left.player_intercepts,
        annotations=left.annotations,
    )

    assert left == right
    assert left.to_json() == right.to_json()
    assert left.content_hash() == right.content_hash()


def test_episode_fixture_turns_are_contiguous() -> None:
    episode = t0_episode()

    assert [turn.turn_id for turn in episode.turns] == [0, 1, 2]
    assert [turn.next_observation.turn_id for turn in episode.turns] == [1, 2, 3]
