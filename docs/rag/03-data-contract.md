# Episode and corpus contract

## Contents

1. Canonical envelope — versioning and strict deserialization.
2. Schema v1 records — current durable semantic types.
3. Turn and episode structure — how records compose.
4. Authoritative versus generated fields — trust boundary.
5. Visibility surfaces — what may reach commander and player.
6. Negative/recovery examples — how failures are represented.
7. Splits and corpus tiers — anti-leakage dataset structure.
8. Canonical JSON and hashes — content identity rules.
9. Machine-readable schema export — JSON Schema interface.
10. Format evolution — refusal and migration policy.

## 1. Canonical envelope

TTT durable records use a common envelope:

```json
{
  "schema": "ttt.commander_observation",
  "schema_version": 1,
  "payload": {}
}
```

The Python implementation lives under
`techrotic_training_triumvirate.schemas`.

Deserialization is strict:

- unknown schema names refuse;
- known schemas with unknown versions refuse;
- unknown payload fields refuse;
- required fields may not disappear silently.

A future breaking format must add a new explicitly supported version and migration path rather than reinterpret v1 data.

## 2. Schema v1 records

The v1 registry currently defines:

| Schema | Purpose |
|---|---|
| `ttt.scenario_identity` | Stable scenario/family/generator/seed identity |
| `ttt.capability` | Generic capability descriptor |
| `ttt.entity` | Generic entity/unit descriptor |
| `ttt.scenario` | Scenario composition, objectives, topology references |
| `ttt.world_private_reference` | Authoritative private-state identity/hash/secret references |
| `ttt.commander_observation` | Student-visible operational observation |
| `ttt.commander_private_context` | Admitted commander-only goals, beliefs, secret references and memory refs |
| `ttt.player_observation` | Human-player-visible world projection |
| `ttt.player_intercept` | Grounded player intercept envelope and explicit deception linkage |
| `ttt.persona` | Structured persona traits, doctrine, constraints and tactical biases |
| `ttt.command_envelope` | Opaque command body + protocol version pending TTT-003 |
| `ttt.communication` | Commander communication output |
| `ttt.assistant_action` | Commands + communications emitted by the student |
| `ttt.interpreter_result` | Authoritative command acceptance/rejection result |
| `ttt.authoritative_event` | Authoritative world/event envelope |
| `ttt.evaluation_annotations` | Evaluation-only labels/hidden annotations |
| `ttt.turn` | One complete semantic interaction turn |
| `ttt.source_provenance` | Source identity/licensing/content provenance |
| `ttt.run_manifest` | Reproducibility/run identity |
| `ttt.episode` | Scenario + persona + initial state + ordered turns + final identity |

Names are intentionally game- and model-family-neutral.

### Command boundary before TTT-003

TTT-002 does **not** define the final command grammar.

`ttt.command_envelope` contains:

- stable `command_id`;
- independent `protocol_version`;
- opaque JSON object `body`.

TTT-003 owns the actual operation IR and may build stricter typed records on top of this envelope without changing unrelated episode schemas.

## 3. Turn and episode structure

A v1 `TurnRecord` composes these independently versioned records:

```text
turn
├── commander observation
├── commander private context
├── assistant action
│   ├── command envelope(s)
│   └── communication(s)
├── interpreter result(s)
├── authoritative world event(s)
├── next commander observation
├── player observation
├── player intercept(s)
└── evaluation annotations
```

The implementation requires:

- `observation.turn_id == turn.turn_id`;
- `next_observation.turn_id == turn.turn_id + 1`;
- episode turns are contiguous and increasing.

An episode is an ordered, replayable sequence bound to:

- schema versions;
- scenario generator/version/seed;
- scenario and persona;
- initial private-world reference/hash;
- event/result sequence;
- final world-state hash;
- run identity/provenance.

## 4. Authoritative versus generated fields

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

## 5. Visibility surfaces

These remain structurally distinct records:

- **world_private:** represented by authoritative state plus `WorldPrivateReference`; never sent to student/player unless explicitly revealed.
- **commander_observation:** exactly what the commander may observe operationally.
- **commander_private_context:** admitted persistent goals/beliefs/secrets/memory for the commander.
- **player_observation:** game-visible state for the human player.
- **player_intercept:** deliberately telegraphed/encoded subset derived from command/event state.
- **evaluation_annotations:** scoring labels available only to evaluation/corpus tooling.

The canonical episode archive may contain all of these records. Model-input/corpus views must select only the admitted surfaces rather than serializing the whole turn blindly.

T0 tests include explicit sentinel values proving commander-private and evaluator-only content does not appear in commander observation, player observation, or player intercept serialization.

## 6. Negative and recovery examples

The corpus must include:

- malformed/invalid commands and the resulting environment feedback;
- syntactically valid but semantically rejected commands;
- accepted commands whose later execution fails;
- correction/replanning demonstrations;
- stale observations;
- partial information;
- secret-bearing contexts with explicit non-disclosure requirements.

When training correction, the input may contain the student's bad prior action plus authoritative feedback; the target is the corrected student action.

TTT-002 ships hand-authored T0 fixtures for:

- ordinary accepted command/dispatch;
- hidden-information preservation;
- rejected/recoverable command.

## 7. Splits and corpus tiers

Prevent leakage by splitting on **world/scenario identity or generator seed families**, not by randomly separating turns from the same episode.

Maintain:

- train;
- development;
- frozen generated evaluation;
- frozen handwritten/adversarial evaluation.

Benchmark seeds/scenarios must never enter training data.

Recommended tiers:

- **T0 schema fixtures:** tiny hand-authored examples for tests.
- **T1 deterministic simulator episodes:** operationally exact; no external model required.
- **T2 teacher-enriched episodes:** T1 plus accepted personality/language/tactical mutations.
- **T3 student-visited corrective episodes:** rollouts from current student with oracle/environment repairs.
- **T4 game-derived traces:** later, normalized traces from real game adapters.

A run manifest records which tiers were used.

## 8. Canonical JSON and hashes

`SchemaRecord.to_json()` uses:

- UTF-8 JSON;
- lexicographically sorted object keys;
- compact separators;
- no NaN or infinity;
- explicit schema/version envelope.

`SchemaRecord.content_hash()` is SHA-256 over that canonical UTF-8 representation.

Mapping insertion order therefore does not change identity. Tests require round-trip semantic equality and hash equality.

LangGraph checkpoint IDs and Concordia execution logs remain supplementary orchestration evidence; they do not replace TTT semantic hashes.

## 9. Machine-readable schema export

The package exports a JSON Schema 2020-12 bundle:

```bash
ttt schema-bundle
ttt schema-bundle --pretty
```

Programmatically:

```python
from techrotic_training_triumvirate.schemas import schema_bundle
```

The bundle is generated from the registered schema names/versions and refuses registry/export drift during tests.

The in-process strict loaders remain authoritative validation for v1 semantics that exceed basic structural JSON Schema constraints, such as deception-link consistency and contiguous turn IDs.

## 10. Format evolution

All durable records carry a schema name/version.

Breaking changes require one of:

1. an explicitly registered new version plus migration/readback support; or
2. clear refusal.

Never silently reinterpret an old corpus.

Command protocol versioning is intentionally independent from episode schema versioning so TTT-003 can evolve command semantics without forcing unrelated record changes.
