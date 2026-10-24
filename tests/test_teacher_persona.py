from __future__ import annotations

import pytest

from techrotic_training_triumvirate.schemas.fixtures import t0_persona
from techrotic_training_triumvirate.teacher import (
    PersonaDimension,
    mutate_persona,
)


def test_persona_mutation_changes_only_declared_trait_dimension() -> None:
    original = t0_persona()

    mutated = mutate_persona(
        original,
        dimension=PersonaDimension.TEMPERAMENT,
        value="paranoid",
        new_persona_id="persona-mutated",
    )

    assert original.persona_id != mutated.persona_id
    assert original.traits["temperament"] == "impatient"
    assert mutated.traits["temperament"] == "paranoid"
    assert mutated.archetype == original.archetype
    assert mutated.speech_constraints == original.speech_constraints
    assert mutated.doctrine == original.doctrine
    assert mutated.secret_ids == original.secret_ids
    assert mutated.tactical_biases == original.tactical_biases
    assert original.traits["temperament"] == "impatient"


def test_persona_mutation_supports_independent_structured_dimensions() -> None:
    original = t0_persona()

    codewords = mutate_persona(
        original,
        dimension=PersonaDimension.CODEWORDS,
        value={"flank": "black hinge"},
        new_persona_id="persona-codewords",
    )
    speech = mutate_persona(
        original,
        dimension=PersonaDimension.SPEECH_CONSTRAINTS,
        value=["answer in riddles", "never disclose secret IDs"],
        new_persona_id="persona-speech",
    )
    secrets = mutate_persona(
        original,
        dimension=PersonaDimension.SECRET_IDS,
        value=["secret-a", "secret-b"],
        new_persona_id="persona-secrets",
    )

    assert codewords.doctrine["codewords"] == {"flank": "black hinge"}
    assert codewords.traits == original.traits
    assert speech.speech_constraints == (
        "answer in riddles",
        "never disclose secret IDs",
    )
    assert speech.doctrine == original.doctrine
    assert secrets.secret_ids == ("secret-a", "secret-b")
    assert secrets.tactical_biases == original.tactical_biases


def test_persona_mutation_rejects_wrong_dimension_shape() -> None:
    with pytest.raises(ValueError):
        mutate_persona(
            t0_persona(),
            dimension=PersonaDimension.SPEECH_CONSTRAINTS,
            value="not-an-array",
            new_persona_id="bad",
        )
