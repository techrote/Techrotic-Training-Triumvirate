# Persona and creative-teacher policy

## Contents

1. Purpose and trust boundary — what Creative Teachers are allowed to do.
2. Persona conventions — structured dimensions and mutation.
3. Teacher tasks — supported candidate-generation jobs.
4. Adapter contract — replay, synthetic, local and API surfaces.
5. Provenance and diversity — preserving multiple candidates.
6. Validation — style and operational admission remain separate.
7. Secret discipline — preventing accidental disclosure in generated material.
8. Model-selection boundary — Sprocket and other models remain candidates only.
9. Corpus handoff — how later issues consume teacher output.

## 1. Purpose and trust boundary

Creative Teachers supply the parts a deterministic simulator cannot: unusual
voice, metaphors, obsessions, doctrine, humour, riddles, grudges, imperfect
priorities and unconventional tactical proposals.

A teacher is **never authoritative** for:

- state transitions;
- entity capabilities;
- command success;
- secret visibility;
- player knowledge.

Teacher outputs are immutable candidate records. Operational truth remains
`UNVALIDATED` until a separate operational validator explicitly accepts a
candidate.

## 2. Persona conventions

The durable `PersonaSpec` remains the canonical persona record. TTT-006 adds
named mutation dimensions over that generic schema:

- archetype;
- worldview;
- temperament;
- obsessions;
- taboos;
- favourites;
- scapegoats;
- humour modes;
- speech constraints;
- codewords;
- secret IDs;
- preferred tactics;
- irrational biases;
- deception propensity;
- persistence;
- volatility.

`mutate_persona()` creates a new persona ID and changes exactly the declared
dimension while copying the other structured fields. This allows controlled
persona families rather than a single fixed "goblin" imitation.

## 3. Teacher tasks

`TeacherTask` currently supports:

| Task | Expected role |
|---|---|
| `event_reaction` | In-character reaction to an admitted event |
| `persona_rewrite` | Rewrite neutral text through a persona voice |
| `codeword_doctrine` | Propose doctrine/codeword mappings |
| `tactical_candidate` | Propose a tactic for later operational validation |
| `persona_invention` | Generate a structured character seed |
| `persona_mutation` | Suggest a controlled persona change |

These tasks create proposals only. For example, a tactical candidate does not
become a command or world event merely because a teacher produced it.

## 4. Adapter contract

`TeacherAdapter` exposes:

- stable `adapter_id`;
- `model_ref`;
- `generate(TeacherRequest) -> TeacherBatch`.

The base package provides:

### ReplayTeacherAdapter

Replays exact recorded candidate specifications for deterministic tests and
readback.

### SyntheticTeacherAdapter

Uses only a seeded local PRNG and fixed templates. It exercises multi-candidate
plumbing, persona styling, provenance and secret redaction without a model.

### LocalModelTeacherStub

Dependency-free placeholder for a future admitted local model runtime.

### ApiTeacherStub

Dependency-free placeholder for a future admitted external service.

The two external stubs refuse execution until configured/admitted. Default CI
therefore performs no model download or network generation.

## 5. Provenance and diversity

Every `TeacherCandidate` carries `TeacherProvenance`:

- adapter ID;
- model/checkpoint reference or deterministic placeholder;
- template version;
- generation/settings object;
- request ID;
- candidate index;
- seed.

Candidate IDs are unique within a batch. Multiple candidates are retained in
order rather than automatically collapsing to one "best" response.

A candidate can be converted to canonical `SourceProvenance`, including a
content hash and the generation metadata. Licensing remains unresolved until a
real model/source is admitted; later corpus admission must apply the licensing
gate.

## 6. Validation

Style and operational validation use distinct protocols.

### Style validation

Examples:

- task/output shape;
- persona constraints;
- forbidden disclosure detection;
- later repetition or lexical-quality checks.

### Operational validation

Examples for later issues:

- proposed entities exist;
- candidate tactic can map to a legal command;
- world capabilities support the proposal;
- proposed factual claims match authoritative state.

If no operational validator is supplied, status is exactly:

```text
UNVALIDATED
```

A stylish or structurally valid teacher response therefore cannot silently
become operational truth.

## 7. Secret discipline

`TeacherRequest` contains an explicit `forbidden_disclosures` list for
request-scoped values that must not appear in candidate text or payloads.

The deterministic synthetic adapter redacts those strings before generating
candidate material. `ForbiddenDisclosureValidator` independently checks the
result surface.

The request also copies its admitted authoritative context on construction.
Adapters receive the copy, not a World Authority object, so teacher code has no
direct mutation path into authoritative world state.

Secret IDs may exist in `PersonaSpec`, but actual hidden values should only be
provided to a teacher when the experiment explicitly requires them.

## 8. Model-selection boundary

Sprocket 500M remains an example/high-interest possible Creative Teacher because
of its observed persistent and surprising persona behaviour. It is **not** a
dependency or selected model.

The same applies to Liquid, Qwen, Gemma/NPC and other models in the candidate
zoo. TTT-011 remains the only model-cast admission gate.

The local/API adapter stubs deliberately use caller-supplied model references
without selecting a checkpoint.

## 9. Corpus handoff

TTT-007 may consume:

- the original `TeacherRequest`;
- all generated `TeacherCandidate` variants;
- candidate provenance/content hashes;
- style-validation decisions;
- operational-validation decisions;
- explicit rejection reasons.

Rejected candidates may remain useful as labelled negative/recovery evidence,
subject to provenance and licensing rules. They must not be silently converted
into ordinary supervised targets.

TTT-007 represents accepted teacher material with a turn-bound
`TeacherEnrichment`. Free-form style text remains separate from
`operational_facts`; every operational claim must be supported by canonical
observation/result/event evidence before admission. The enrichment source ID must
resolve to canonical SourceProvenance and model/external teacher output remains
quarantined until its license disposition is explicitly admitted.
