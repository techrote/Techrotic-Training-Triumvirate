from __future__ import annotations

import pytest

pytest.importorskip("concordia")

from techrotic_training_triumvirate.world import (
    ScenarioConfig,
    ScenarioGenerator,
    run_envelopes,
    run_scripted_episode,
)
from techrotic_training_triumvirate.world.concordia_host import (
    concordia_identity,
    run_concordia_envelopes,
)


def test_concordia_host_matches_direct_ttt_semantics() -> None:
    seed = 24301
    scripted = run_scripted_episode(seed=seed, turns=3)
    blueprint = ScenarioGenerator().generate(
        seed=seed,
        config=ScenarioConfig(),
    )

    direct = run_envelopes(blueprint, scripted.envelopes)
    hosted = run_concordia_envelopes(blueprint, scripted.envelopes)

    assert concordia_identity() == "2.4.0"
    assert hosted.final_state_hash == direct.final_state_hash
    assert hosted.event_hash == direct.event_hash
    assert hosted.commander_observation_hash == direct.commander_observation_hash
    assert hosted.player_observation_hash == direct.player_observation_hash
    assert hosted.events == direct.events
