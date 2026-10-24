# Architecture

## Contents

1. System boundaries — what is authoritative and what is learned.
2. Data flow — how scenarios become training episodes.
3. Runtime flow — how a trained commander interacts with actors.
4. Component contracts — stable interfaces between modules.
5. Hidden-information surfaces — private, observed, and player-visible state.
6. Failure handling — how errors become training signal.
7. Extension points — where model families and games plug in.

## 1. System boundaries

### World Authority

Deterministic, replayable code owns:
- scenario state;
- unit identities/capabilities/resources;
- command validation;
- accepted/rejected order state;
- abstract movement/combat/objective transitions;
- error codes and structured feedback;
- secrets and visibility;
- authoritative event log.

It may use probabilistic simulation only when randomness is seeded and replayable.

### Creative Teacher

Untrusted, pluggable generator may:
- propose character utterances;
- rewrite semantically equivalent messages;
- invent persona traits and doctrine vocabulary;
- propose tactical candidate actions;
- create riddles, insults, rituals, codewords, and eccentric motives.

Teacher proposals enter admitted data only after validation. Teacher-generated world results never override World Authority.

### Student Commander

Receives only the admitted commander observation plus its allowed durable memory/context. Produces:
- typed command/action objects;
- optional commander speech/radio;
- optional rationale only when a training/evaluation mode explicitly requests it.

Its output is parsed and validated before the World Authority executes anything.

## 2. Data flow

```
scenario seed/spec
      |
      v
World Authority -----> authoritative event/result stream
      |                          |
      | observation              | validated facts/errors
      v                          v
teacher/oracle ---> candidate action + style mutation
      |                          |
      +---------- validators ----+
                    |
                    v
          canonical episode record
                    |
        provenance / dedup / split
                    |
                    v
             training corpus
```

A teacher can improve *how* an action is expressed or suggest an action to test, but the environment determines whether that action is valid and what follows.

## 3. Runtime flow

```
game/abstract state
   -> observation adapter
   -> Student Commander
   -> command parser/schema
   -> deterministic interpreter
   -> squad/actor objective adapter
   -> authoritative game execution
   -> structured feedback/event log
   -> next observation
```

Player intercept rendering consumes the **dispatched authoritative command/event stream**, not free-standing hallucinated hints.

## 4. Component contracts

Implement modules behind interfaces rather than a monolith:

- `ScenarioGenerator`
- `World` / `WorldState`
- `ObservationBuilder`
- `CommandInterpreter`
- `SessionRecorder`
- `TeacherAdapter`
- `StudentAdapter`
- `CorpusAssembler`
- `EpisodeValidator`
- `InterceptEncoder`
- `Evaluator`
- `RunManifest`

### Orchestration substrate

SPIKE-LG-001 / issue #18 proved LangGraph checkpoint → historical branch/update → correction → replay around a deterministic TTT-style World Authority. The spike decision is to **adopt LangGraph for generic orchestration/checkpoint/branch/replay**, especially TTT-005 session work and TTT-010 corrective rollouts.

This does not make LangGraph state canonical TTT state. TTT-owned schemas remain authoritative for command meaning, world semantics, hidden-information views, event records, semantic hashes, corpus identity, and experiment provenance. The deterministic World Authority must remain callable/testable without LangGraph so orchestration can be replaced independently.

Use LangGraph checkpoints to answer *where/how should execution resume or fork?* Use TTT records to answer *what semantically happened, under which contracts and evidence?*

Spike evidence and tested implementation: `docs/spikes/langgraph-checkpoint-branch-replay.md`.

### Optional simulation substrate

SPIKE-CD-001 / issue #20 proved that Concordia v2.4.0 can run a deterministic non-LLM Game Master through its real Sequential engine while routing JSON actions into strict TTT typed commands and preserving distinct world-private, commander-visible, and player-visible surfaces.

The decision is **conditional adoption**: Concordia may host richer TTT simulations when its entity, scene, scheduling, or Game-Master machinery is useful, but it is not the mandatory World Authority implementation.

TTT's World Authority must remain framework-neutral and directly callable without Concordia or LangGraph. Keep a lightweight native/direct execution path for fast tests and corpus generation. If Concordia is used, treat its string entity/action boundary as transport only; parse into TTT typed commands before mutation, disable/fail closed on LLM fallback in authoritative GM paths, and treat Concordia logs/checkpoints as supplementary rather than canonical provenance.

Spike evidence and tested implementation: `docs/spikes/concordia-deterministic-gm-visibility.md`.

Serialized contracts must be versioned.

## 5. Hidden-information surfaces

Maintain distinct views:

- **world_private:** complete authoritative state; never sent to student/player unless explicitly revealed.
- **commander_observation:** exactly what the commander may know.
- **commander_private_memory:** admitted persistent beliefs/goals/secrets for the commander.
- **player_observation:** game-visible state.
- **player_intercept:** deliberately telegraphed/encoded subset of actual enemy command events.
- **evaluation_annotations:** labels used only by scoring code.

Tests must detect accidental inclusion of forbidden fields.

## 6. Failure handling

Failures are first-class:
- syntax/schema failure;
- unknown entity;
- stale entity/version;
- capability mismatch;
- unavailable/dead unit;
- invalid target;
- impossible/precondition failure;
- resource failure;
- command accepted but execution later fails;
- timeout/stall/no-progress;
- contradictory/overlapping order;
- hidden-information violation.

The student should be exposed to both immediate interpreter errors and later execution failures.

## 7. Extension points

Model adapters must support local checkpoints and recorded fixtures without requiring network access. The programme may later admit API teachers or different students.

Game adapters should convert game-specific state/actions into the canonical observation/command/event contracts. The abstract simulator remains a fast training/evaluation environment, not a claim of full physical equivalence.
