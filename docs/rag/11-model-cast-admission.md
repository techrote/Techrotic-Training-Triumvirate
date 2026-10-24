# Initial model-cast admission

## Status

**UNSELECTED.**

The programme intentionally publishes before choosing the initial teacher/student model lineup.

A non-authoritative first-pass candidate shelf and characterization plan is recorded in [12-candidate-model-zoo.md](12-candidate-model-zoo.md). That shortlist is planning material only: **it does not constitute owner admission of any model**.

No implementation agent may infer a selection from discussion, examples, the candidate shelf, or repository dependencies. The selection becomes authoritative only when this document or the linked TTT-011 issue records it explicitly.

## Roles to select

| Role | Selection |
|---|---|
| Creative teacher A | TBD |
| Creative teacher B / comparison | TBD / optional |
| Primary compact student | TBD |
| Larger student challenger | TBD / optional |
| Operational model-assisted oracle | None by default; deterministic preferred |
| WorldTUI-derived checkpoint experiment | TBD / optional |

## Candidate-characterization input

TTT-011 should use `12-candidate-model-zoo.md` as the starting shortlist unless the owner revises it.

The current plan intentionally emphasizes small models first:

- extreme-small and 1.2B Liquid baselines;
- LFM2.5-2.6B;
- LFM2.5-8B-A1B low-active-parameter MoE;
- Qwen3.5-4B;
- Think.NPC-1B;
- Qwen-3B-Intent-Microplan-v2;
- Gemma NPC variants;
- Sprocket as a possible separate creative reference if an artifact is admitted.

The first decision should be informed by a common characterization battery rather than model reputation alone.

## Candidate record template

For each considered model record:
- exact model/repository/revision;
- parameter count and active-parameter count where applicable;
- exact GGUF/native artifact filenames and hashes;
- context;
- tokenizer/chat/tool format;
- license and output/training-use disposition;
- local inference backend;
- structured-output probe result;
- persona/spontaneity probe result;
- secret-discipline probe result;
- recovery/multi-turn probe result;
- runtime memory/latency/tokens-per-second measurement;
- fine-tuning method compatibility;
- redistribution/export constraints.

## Selection criteria

The cast should maximize the experiment's information value, not simply benchmark strength.

Prefer candidates that let us test:
- whether eccentric teacher behaviour transfers;
- whether command competence and personality can coexist;
- whether a sub-billion or ~1B student is sufficient;
- whether additional capacity materially improves multi-turn recovery;
- whether low-active-parameter MoE models offer a useful speed/capability trade;
- whether NPC-specialized pretraining/tuning improves behaviour beyond general models;
- whether a WorldTUI-derived representation/checkpoint adds value beyond its methodology.

## Decision block

When the owner selects the initial cast, replace this placeholder:

```yaml
decision_status: UNSELECTED
decision_date: null
creative_teachers: []
primary_student: null
challenger_students: []
worldtui_checkpoint_experiment: null
training_budget: null
runtime_targets: null
notes: null
```

TTT-011 should then verify immutable revisions/licenses, run cheap probes, and merge the final admission record before TTT-012 begins.
