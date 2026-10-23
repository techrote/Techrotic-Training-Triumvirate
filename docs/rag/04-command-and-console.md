# Command and console protocol

## Design principle

The commander issues **high-level typed intent**, not arbitrary executable scripts and not low-level body forces.

Example conceptual command:

```json
{
  "op": "assign_objective",
  "unit": "squad_3",
  "objective": {
    "kind": "flank",
    "target": "reactor_east",
    "approach": "north"
  },
  "constraints": {
    "urgency": "high",
    "avoid": ["zone_flooded"]
  }
}
```

The interpreter validates it and emits a structured result.

## Initial operation family

Keep the first vocabulary small and composable. Candidate operations:
- inspect/query;
- assign objective;
- set/modify constraints;
- coordinate/synchronize;
- hold/cancel/recall;
- transmit/communicate;
- request status.

Exact names and schemas are implemented under TTT-003 and versioned. Avoid prematurely encoding game-specific actors into the grammar.

## Error model

Errors are machine-readable with stable codes plus optional human/character-neutral explanation. Examples:
- `SCHEMA_INVALID`
- `ENTITY_UNKNOWN`
- `ENTITY_UNAVAILABLE`
- `CAPABILITY_MISMATCH`
- `TARGET_INVALID`
- `PRECONDITION_FAILED`
- `RESOURCE_EXHAUSTED`
- `STALE_OBSERVATION`
- `ORDER_CONFLICT`

Later execution events distinguish an accepted order from an achieved outcome.

## Console/session surface

"Console" means the model-visible interaction surface, not necessarily an ANSI terminal emulator.

It should support:
- compact observation rendering;
- structured and/or text views generated from the same canonical state;
- deterministic acknowledgements/errors;
- incremental/delta representations for changed facts;
- multiple turn/session history;
- configurable verbosity;
- exact reconstruction of a recorded episode.

A WorldTUI-style row/frame representation may be an experiment, but canonical data must not depend on presentation pixels/rows.

## Stateful synthetic sessions

Scenario generators should create coherent multi-turn activities rather than independent prompts. Randomize:
- map/topology;
- actors/capabilities;
- objectives;
- resources;
- timing;
- visibility;
- names/callsigns;
- doctrine vocabulary;
- failures and interruptions.

Some episodes should start mid-state to reduce overfitting to clean initial conditions.

## Interpreter boundary

The interpreter:
1. parses/validates against the command schema;
2. resolves entity references;
3. checks capabilities/preconditions/resources;
4. converts accepted high-level intent into authoritative world orders;
5. records dispatch events;
6. returns structured feedback.

It must not execute arbitrary host commands from model strings.

## Recovery data

When a command is rejected, preserve:
- the command attempted;
- exact structured error;
- observation revision if any;
- corrected action;
- downstream result.

These are high-value examples for tool-use competence.

## Runtime compatibility

Game-specific bridges map the canonical high-level order into squad/actor controllers. The core command protocol should remain stable enough that synthetic training does not have to reproduce every game physics detail.
