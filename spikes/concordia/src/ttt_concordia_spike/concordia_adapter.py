"""Concordia adapter with a deterministic, non-LLM Game Master."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
import functools
import json
from typing import Any

from concordia.agents import entity_agent_with_logging
from concordia.components.game_master import event_resolution
from concordia.components.game_master import switch_act
from concordia.environment import engine as engine_lib
from concordia.language_model import no_language_model
from concordia.typing import entity as entity_lib
from concordia.typing import entity_component

from .world import TttCommand, WorldAuthority


class ExplodingLanguageModel(no_language_model.NoLanguageModel):
    """Fails immediately if any supposedly deterministic GM path samples."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def sample_text(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        terminators: Collection[str] = (),
        temperature: float = 1.0,
        top_p: float = 0.95,
        top_k: int = 50,
        timeout: float = 60.0,
        seed: int | None = None,
    ) -> str:
        del prompt, max_tokens, terminators, temperature, top_p, top_k, timeout, seed
        self.calls += 1
        raise AssertionError("Concordia attempted an LLM text sample in deterministic GM.")

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, Mapping[str, Any]]:
        del prompt, responses, seed
        self.calls += 1
        raise AssertionError("Concordia attempted an LLM choice sample in deterministic GM.")


class _StatelessComponent(entity_component.ContextComponent):
    def get_state(self) -> entity_component.ComponentState:
        return {}

    def set_state(self, state: entity_component.ComponentState) -> None:
        del state


class DeterministicTerminate(_StatelessComponent):
    def pre_act(self, action_spec: entity_lib.ActionSpec) -> str:
        if action_spec.output_type == entity_lib.OutputType.TERMINATE:
            return entity_lib.BINARY_OPTIONS["negative"]
        return ""


class FixedNextActing(_StatelessComponent):
    def pre_act(self, action_spec: entity_lib.ActionSpec) -> str:
        if action_spec.output_type == entity_lib.OutputType.NEXT_ACTING:
            return "Commander"
        return ""


class TypedCommandActionSpec(_StatelessComponent):
    def pre_act(self, action_spec: entity_lib.ActionSpec) -> str:
        if action_spec.output_type != entity_lib.OutputType.NEXT_ACTION_SPEC:
            return ""
        return engine_lib.action_spec_to_string(
            entity_lib.ActionSpec(
                call_to_action="Return exactly one TTT command JSON object.",
                output_type=entity_lib.OutputType.FREE,
                tag="ttt-command",
            )
        )


class VisibilityRouter(_StatelessComponent):
    def __init__(self, world: WorldAuthority) -> None:
        super().__init__()
        self._world = world

    def pre_act(self, action_spec: entity_lib.ActionSpec) -> str:
        if action_spec.output_type != entity_lib.OutputType.MAKE_OBSERVATION:
            return ""
        call = action_spec.call_to_action
        if "Commander" in call:
            payload = {"surface": "commander", "state": self._world.commander_view()}
        elif "Player" in call:
            payload = {"surface": "player", "state": self._world.player_view()}
        else:
            raise ValueError(f"Unknown observation target in {call!r}.")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class DeterministicResolution(_StatelessComponent):
    def __init__(self, world: WorldAuthority) -> None:
        super().__init__()
        self._world = world
        self._putative_event = ""
        self.last_command: TttCommand | None = None

    def pre_observe(self, observation: str) -> str:
        prefix = event_resolution.PUTATIVE_EVENT_TAG
        if observation.startswith(prefix):
            self._putative_event = observation[len(prefix):].strip()
        return ""

    def pre_act(self, action_spec: entity_lib.ActionSpec) -> str:
        if action_spec.output_type != entity_lib.OutputType.RESOLVE:
            return ""
        if not self._putative_event:
            raise RuntimeError("No putative event to resolve.")
        raw = self._putative_event
        if raw.startswith("Commander:"):
            raw = raw.split(":", 1)[1].strip()
        command = TttCommand.from_json(raw)
        self.last_command = command
        result = self._world.resolve(command)
        self._putative_event = ""
        return json.dumps(
            {"command": command.to_dict(), "resolution": result.to_dict()},
            sort_keys=True,
            separators=(",", ":"),
        )

    def get_state(self) -> entity_component.ComponentState:
        return {"putative_event": self._putative_event}

    def set_state(self, state: entity_component.ComponentState) -> None:
        self._putative_event = str(state.get("putative_event", ""))


class ScriptedEntity(entity_lib.Entity):
    """Minimal Concordia entity used to prove engine integration."""

    def __init__(self, name: str, actions: Sequence[str] = ()) -> None:
        self._name = name
        self._actions = list(actions)
        self.observations: list[str] = []

    @functools.cached_property
    def name(self) -> str:
        return self._name

    def act(self, action_spec: entity_lib.ActionSpec = entity_lib.DEFAULT_ACTION_SPEC) -> str:
        if not self._actions:
            raise AssertionError(f"{self.name} was unexpectedly asked to act.")
        action = self._actions.pop(0)
        action_spec.validate(action)
        return action

    def observe(self, observation: str) -> None:
        self.observations.append(observation)


def build_game_master(
    world: WorldAuthority,
    model: ExplodingLanguageModel,
) -> tuple[entity_agent_with_logging.EntityAgentWithLogging, DeterministicResolution]:
    resolution = DeterministicResolution(world)
    components: dict[str, entity_component.ContextComponent] = {
        switch_act.DEFAULT_TERMINATE_COMPONENT_KEY: DeterministicTerminate(),
        switch_act.DEFAULT_MAKE_OBSERVATION_COMPONENT_KEY: VisibilityRouter(world),
        switch_act.DEFAULT_NEXT_ACTING_COMPONENT_KEY: FixedNextActing(),
        switch_act.DEFAULT_NEXT_ACTION_SPEC_COMPONENT_KEY: TypedCommandActionSpec(),
        switch_act.DEFAULT_RESOLUTION_COMPONENT_KEY: resolution,
    }
    act_component = switch_act.SwitchAct(
        model=model,
        entity_names=("Commander", "Player"),
    )
    gm = entity_agent_with_logging.EntityAgentWithLogging(
        agent_name="TTT World Authority",
        act_component=act_component,
        context_components=components,
    )
    return gm, resolution
