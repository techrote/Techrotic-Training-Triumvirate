from __future__ import annotations

import pytest

from techrotic_training_triumvirate.determinism import stable_u64_sequence

RECORDED_SEED_0X5EED = (
    15774859062804099852,
    7519841847863157723,
    10781327723028660938,
    15125954683616293964,
    11818232279212408285,
)


def test_seeded_sequence_repeats_exactly(deterministic_seed: int) -> None:
    first = stable_u64_sequence(deterministic_seed, 5)
    second = stable_u64_sequence(deterministic_seed, 5)

    assert first == second
    assert first == RECORDED_SEED_0X5EED


def test_different_seed_changes_sequence(deterministic_seed: int) -> None:
    assert stable_u64_sequence(deterministic_seed + 1, 5) != RECORDED_SEED_0X5EED


def test_negative_sequence_count_refuses() -> None:
    with pytest.raises(ValueError, match="count must be non-negative"):
        stable_u64_sequence(1, -1)
