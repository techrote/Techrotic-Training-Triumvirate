"""Structured persona conventions and one-dimension mutation helpers."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum

from techrotic_training_triumvirate.schemas import JsonValue, PersonaSpec

from .model import clone_json_object


class PersonaDimension(str, Enum):
    ARCHETYPE = "archetype"
    WORLDVIEW = "worldview"
    TEMPERAMENT = "temperament"
    OBSESSIONS = "obsessions"
    TABOOS = "taboos"
    FAVOURITES = "favourites"
    SCAPEGOATS = "scapegoats"
    HUMOUR_MODES = "humour_modes"
    SPEECH_CONSTRAINTS = "speech_constraints"
    CODEWORDS = "codewords"
    SECRET_IDS = "secret_ids"
    PREFERRED_TACTICS = "preferred_tactics"
    IRRATIONAL_BIASES = "irrational_biases"
    DECEPTION_PROPENSITY = "deception_propensity"
    PERSISTENCE = "persistence"
    VOLATILITY = "volatility"


_TRAIT_DIMENSIONS = {
    PersonaDimension.WORLDVIEW,
    PersonaDimension.TEMPERAMENT,
    PersonaDimension.OBSESSIONS,
    PersonaDimension.TABOOS,
    PersonaDimension.FAVOURITES,
    PersonaDimension.SCAPEGOATS,
    PersonaDimension.HUMOUR_MODES,
}
_TACTICAL_DIMENSIONS = {
    PersonaDimension.PREFERRED_TACTICS,
    PersonaDimension.IRRATIONAL_BIASES,
    PersonaDimension.DECEPTION_PROPENSITY,
    PersonaDimension.PERSISTENCE,
    PersonaDimension.VOLATILITY,
}


def _string_tuple(
    value: JsonValue,
    *,
    dimension: PersonaDimension,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{dimension.value} requires an array of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{dimension.value} requires an array of strings")
        if not item.strip():
            raise ValueError(f"{dimension.value} entries must not be empty")
        result.append(item)
    return tuple(result)


def mutate_persona(
    persona: PersonaSpec,
    *,
    dimension: PersonaDimension,
    value: JsonValue,
    new_persona_id: str,
) -> PersonaSpec:
    """Return a new persona with exactly one declared dimension changed."""
    if not new_persona_id.strip():
        raise ValueError("new_persona_id must not be empty")
    traits = clone_json_object(persona.traits)
    doctrine = clone_json_object(persona.doctrine)
    tactical_biases = clone_json_object(persona.tactical_biases)

    if dimension is PersonaDimension.ARCHETYPE:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("archetype requires a non-empty string")
        return replace(persona, persona_id=new_persona_id, archetype=value)

    if dimension in _TRAIT_DIMENSIONS:
        traits[dimension.value] = value
        return replace(persona, persona_id=new_persona_id, traits=traits)

    if dimension in _TACTICAL_DIMENSIONS:
        tactical_biases[dimension.value] = value
        return replace(
            persona,
            persona_id=new_persona_id,
            tactical_biases=tactical_biases,
        )

    if dimension is PersonaDimension.SPEECH_CONSTRAINTS:
        return replace(
            persona,
            persona_id=new_persona_id,
            speech_constraints=_string_tuple(value, dimension=dimension),
        )

    if dimension is PersonaDimension.CODEWORDS:
        if not isinstance(value, dict):
            raise ValueError("codewords requires a JSON object")
        doctrine["codewords"] = clone_json_object(value)
        return replace(persona, persona_id=new_persona_id, doctrine=doctrine)

    if dimension is PersonaDimension.SECRET_IDS:
        return replace(
            persona,
            persona_id=new_persona_id,
            secret_ids=_string_tuple(value, dimension=dimension),
        )

    raise AssertionError(f"unhandled persona dimension: {dimension}")
