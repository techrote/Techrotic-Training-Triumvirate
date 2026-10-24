"""Grounded deterministic player-intercept encoder."""

from __future__ import annotations

from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    JsonObject,
    PlayerInterceptEnvelope,
    SchemaValidationError,
)

from .model import (
    INTERCEPT_CODEC_VERSION,
    DoctrineLexicon,
    SemanticIntercept,
    false_semantics_from_event,
)
from .policy import InterceptPolicy, apply_semantic_policy, render_semantics


def _payload(
    *,
    source_kind: str,
    event_id: str,
    source_tick: int,
    fields: JsonObject,
    doctrine: DoctrineLexicon,
    policy: InterceptPolicy,
) -> JsonObject:
    visible = apply_semantic_policy(
        fields,
        event_id=event_id,
        doctrine=doctrine,
        policy=policy,
    )
    rendered = render_semantics(
        visible,
        event_id=event_id,
        policy=policy,
    )
    return {
        "codec_version": INTERCEPT_CODEC_VERSION,
        "doctrine_id": doctrine.doctrine_id,
        "doctrine_version": doctrine.version,
        "policy_id": policy.policy_id,
        "policy_version": policy.version,
        "source_kind": source_kind,
        "source_tick": source_tick,
        "available_tick": source_tick + policy.delay_ticks,
        "semantic": visible,
        "rendered": rendered,
    }


class InterceptEncoder:
    """Encode real dispatch/deception events into grounded player intercepts."""

    def __init__(
        self,
        *,
        doctrine: DoctrineLexicon,
        policy: InterceptPolicy,
    ) -> None:
        self._doctrine = doctrine
        self._policy = policy

    def encode(self, event: AuthoritativeEvent) -> PlayerInterceptEnvelope:
        if event.kind == "command-dispatched":
            semantic = SemanticIntercept.from_dispatch_event(event)
            return PlayerInterceptEnvelope(
                intercept_id=f"intercept:{event.event_id}",
                source_event_ids=(event.event_id,),
                payload=_payload(
                    source_kind=event.kind,
                    event_id=event.event_id,
                    source_tick=event.tick,
                    fields=semantic.fields,
                    doctrine=self._doctrine,
                    policy=self._policy,
                ),
                is_deception=False,
                deception_event_id=None,
            )

        if event.kind == "deception-broadcast":
            real_event_id = event.data.get("real_dispatch_event_id")
            if not isinstance(real_event_id, str) or not real_event_id:
                raise SchemaValidationError(
                    "deception broadcast requires real_dispatch_event_id"
                )
            fields = false_semantics_from_event(event)
            return PlayerInterceptEnvelope(
                intercept_id=f"intercept:{event.event_id}",
                source_event_ids=(event.event_id, real_event_id),
                payload=_payload(
                    source_kind=event.kind,
                    event_id=event.event_id,
                    source_tick=event.tick,
                    fields=fields,
                    doctrine=self._doctrine,
                    policy=self._policy,
                ),
                is_deception=True,
                deception_event_id=event.event_id,
            )

        raise SchemaValidationError(
            "intercepts require command-dispatched or deception-broadcast events"
        )
