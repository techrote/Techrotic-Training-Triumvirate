from __future__ import annotations

import pytest

from techrotic_training_triumvirate.determinism import DEFAULT_TEST_SEED


@pytest.fixture
def deterministic_seed() -> int:
    """Explicit seed fixture for deterministic tests."""
    return DEFAULT_TEST_SEED
