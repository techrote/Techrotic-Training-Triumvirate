# Player intercepts and tactical telegraphing

## Purpose

Enemy command traffic should be both an AI-control artifact and a gameplay surface. The player may overhear encoded, partial, stylized communications and learn to infer enemy doctrine.

## Grounding rule

A normal intercept is derived from an **actual authoritative dispatched command/event**.

Flow:

```
validated commander command
  -> authoritative dispatch event
  -> semantic intercept payload
  -> faction/persona codec
  -> information-loss/redaction policy
  -> player-visible text/audio/event
```

This prevents decorative dialogue from falsely telegraphing actions the enemy will not attempt.

## Semantic payload

Before styling, represent what may be revealed:
- sender/callsign class;
- receiver/unit class;
- objective/action class;
- target alias;
- route/direction;
- synchronization trigger;
- urgency;
- optional timing;
- confidence/noise.

Visibility policy chooses the subset.

## Codewords and doctrine

A faction/persona may map stable concepts to codewords:
- formation names;
- compass metaphors;
- unit nicknames;
- objective categories;
- timing rituals.

Mappings belong to versioned world/doctrine data so repeated phrases can genuinely teach the player something.

## Controlled ambiguity

Interception may:
- redact fields;
- corrupt tokens;
- substitute aliases;
- reveal only part of a compound order;
- delay delivery;
- vary linguistic rendering.

It must not accidentally expose commander-private secrets beyond policy.

## Explicit deception

False broadcasts are permitted only when deception is an explicit authoritative commander action/event. The system records:
- deceptive message;
- intended false semantic payload;
- real command separately;
- who can observe each.

This allows the player to be lied to *by the enemy*, rather than by an inconsistent implementation.

## Training use

Intercepts can be part of synthetic data in several ways:
- teach commander-compatible doctrine vocabulary;
- test secret preservation;
- train communication style;
- evaluate consistency between dispatched orders and public signals.

Do not require the student to reproduce exact cosmetic wording unless that is an explicit experiment; semantic correctness and character may be scored separately.
