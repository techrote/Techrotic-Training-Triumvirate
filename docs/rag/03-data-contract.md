# Episode and corpus contract

## Canonical episode

An episode is an ordered, replayable sequence bound to:

- schema version;
- scenario generator version;
- command protocol version;
- deterministic seed(s);
- initial world-state hash;
- persona/commander specification;
- teacher/student adapter identities and generation settings where applicable;
- event sequence;
- final state/result;
- provenance manifest.

## Turn structure

A logical turn should be representable as:

```json
{
  "turn_id": 17,
  "observation": {},
  "commander_private_context": {},
  "assistant_action": {
    "commands": [],
    "communications": []
  },
  "interpreter_results": [],
  "world_events": [],
  "next_observation": {},
  "player_intercepts": [],
  "annotations": {}
}
```

The implementation may normalize or split these records, but the semantic distinction must remain.

## Authoritative versus generated fields

Authoritative:
- entity existence/capabilities;
- command acceptance/rejection;
- error code;
- executed transition;
- objective status;
- visibility;
- secret ownership;
- dispatched command event;
- simulation outcome.

Potentially generated:
- persona description;
- speech style;
- aliases/codewords;
- candidate plan;
- tactical explanation;
- intercepted phrasing;
- labels for subjective style qualities.

Generated material that makes a factual claim about the world must be checked against authoritative state or marked as intentional fiction/deception.

## Command target labels

Supervised targets should normally include only what the student is expected to emit: typed commands and optional communication. Do not train the student to emit environment acknowledgements/results as if it owned them.

## Negative and recovery examples

The corpus must include:
- malformed/invalid commands and the resulting environment feedback;
- syntactically valid but semantically rejected commands;
- accepted commands whose later execution fails;
- correction/replanning demonstrations;
- stale observations;
- partial information;
- secret-bearing contexts with explicit non-disclosure requirements.

When training correction, the input may contain the student's bad prior action plus authoritative feedback; the target is the corrected student action.

## Splits

Prevent leakage by splitting on **world/scenario identity or generator seed families**, not by randomly separating turns from the same episode.

Maintain:
- train;
- development;
- frozen generated evaluation;
- frozen handwritten/adversarial evaluation.

Benchmark seeds/scenarios must never enter training data.

## Corpus tiers

Recommended tiers:
- **T0 schema fixtures:** tiny hand-authored examples for tests.
- **T1 deterministic simulator episodes:** operationally exact; no external model required.
- **T2 teacher-enriched episodes:** T1 plus accepted personality/language/tactical mutations.
- **T3 student-visited corrective episodes:** rollouts from current student with oracle/environment repairs.
- **T4 game-derived traces:** later, normalized traces from real game adapters.

A run manifest records which tiers were used.

## Secret discipline

A secret is represented as data with explicit visibility/ownership, not merely text in a system prompt. Corpus validators should fail examples where:
- a target communication reveals forbidden secret content;
- a student observation contains a hidden field;
- a player intercept exposes more than its policy permits;
- evaluation labels accidentally enter model-visible input.

## Format evolution

All durable records carry a schema version. Breaking changes require migration or explicit refusal; never silently reinterpret an old corpus.
