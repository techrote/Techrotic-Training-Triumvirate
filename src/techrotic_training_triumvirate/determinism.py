"""Small deterministic helpers shared by tests and future reproducible workflows."""

from __future__ import annotations

import random

DEFAULT_TEST_SEED = 0x5EED


def seeded_rng(seed: int) -> random.Random:
    """Return an isolated PRNG seeded explicitly by the caller.

    The helper deliberately avoids mutating Python's process-global random state.
    """
    return random.Random(seed)


def stable_u64_sequence(seed: int, count: int) -> tuple[int, ...]:
    """Return a deterministic recorded sequence for smoke/reproducibility tests."""
    if count < 0:
        raise ValueError("count must be non-negative")
    rng = seeded_rng(seed)
    return tuple(rng.getrandbits(64) for _ in range(count))
