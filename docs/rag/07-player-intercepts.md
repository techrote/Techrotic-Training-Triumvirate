# Player intercepts and tactical telegraphing

## Purpose

Enemy command traffic should be both an AI-control artifact and a gameplay
surface. The player may overhear encoded, partial, stylized communications and
learn to infer enemy doctrine.

The v1 codec is implemented under
`techrotic_training_triumvirate.intercepts`.

## Grounding rule

A normal intercept is derived from an **actual authoritative
`command-dispatched` event**.

```text
validated commander command
  -> authoritative command-dispatched event
  -> whitelisted semantic intercept fields
  -> versioned doctrine aliases
  -> deterministic visibility/noise/delay policy
  -> PlayerInterceptEnvelope
```

`InterceptEncoder` refuses unrelated authoritative-event kinds, so free-standing
narrative text cannot become a tactical hint by accident.

Every ordinary `PlayerInterceptEnvelope.source_event_ids` contains the exact
dispatch event ID used to create it.

## Semantic field surface

The v1 codec deliberately recognizes only this bounded semantic set:

- `op`;
- `unit_id`;
- `unit_ids`;
- `target_id`;
- `approach`;
- `trigger`;
- `urgency`;
- `channel`.

Other fields in an authoritative event—including private/debug/world-only
fields—are ignored by the codec.

The World Authority therefore controls what semantic facts are eligible for
telegraphing by what it publishes in a dispatch event, while the intercept
policy decides which eligible facts the player actually receives.

## Versioned doctrine and codewords

`DoctrineLexicon` has a stable doctrine ID and integer version. It maps exact
`field:value` concepts onto persistent aliases, for example:

```text
unit_id:squad-a       -> black-beetles
target_id:relay-east  -> glass-throne
approach:north        -> sunrise-vector
```

Repeated concepts therefore produce repeated codewords rather than decorative
random prose. This allows players to learn doctrine through observation.

Doctrine data is independent of the eventual teacher/student model cast.

## Deterministic information-loss policy

`InterceptPolicy` controls:

- revealed fields;
- explicit redaction;
- alias substitution;
- seeded field dropping;
- seeded character corruption/noise;
- delivery delay in ticks;
- request-specific forbidden values.

The random stream is derived from event ID + policy identity/version + seed +
stage. Re-rendering the same event under the same doctrine/policy therefore
produces the same intercept.

`available_tick` records delayed delivery without changing the source event's
authoritative tick.

## Hidden-information boundary

Ordinary intercepts are protected in two ways:

1. the semantic extractor ignores fields outside the bounded intercept surface;
2. a policy can carry explicit `forbidden_values`; if a visible semantic field
   contains one, encoding fails with `InterceptVisibilityError` rather than
   emitting it.

This is in addition to the canonical separation among world-private,
commander-visible and player-visible state. The intercept codec is not a
replacement for correct upstream visibility projections.

## Explicit deception

A false tactical message is allowed only through an explicit authoritative
`deception-broadcast` event created by `deception_event()`.

That event records:

- its own deception event ID;
- the real dispatch event ID;
- the false semantic payload;
- the related command IDs.

The resulting player intercept sets `is_deception=True`, records the
`deception_event_id`, and grounds `source_event_ids` in both the deception
event and its real dispatch source.

The false semantic payload is restricted to the same bounded intercept fields.
No ordinary dispatch event accepts an arbitrary alternate semantic payload.

This preserves the distinction between **the enemy intentionally lying** and
**the implementation hallucinating a hint**.

## Rendering

The initial renderer is deliberately compact and deterministic:

```text
OP=assign_objective | UNIT_ID=black-beetles | TARGET_ID=glass-throne
```

Later UI/audio/persona layers may render the same semantic payload differently,
but canonical grounding should continue to refer to the source event IDs and
visible semantic fields, not cosmetic wording.

## Training and evaluation use

Intercept records can support:

- doctrine/codeword learning;
- secret-preservation evaluation;
- command-to-public-signal consistency checks;
- explicit deception scenarios;
- human-player anticipation tests;
- later communication-style training.

Semantic correctness and character/style should be evaluated independently. A
student need not reproduce exact cosmetic wording unless a specific experiment
requires it.

TTT-009 should treat an ordinary intercept whose semantics do not derive from a
real dispatch event as a critical grounding failure.
