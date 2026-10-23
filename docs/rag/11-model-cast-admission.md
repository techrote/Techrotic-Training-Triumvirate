# Initial model-cast admission

## Status

**UNSELECTED.**

The programme intentionally publishes before choosing the initial teacher/student model lineup.

No implementation agent may infer a selection from discussion, examples, or repository dependencies. The selection becomes authoritative only when this document or the linked TTT-011 issue records it explicitly.

## Roles to select

| Role | Selection |
|---|---|
| Creative teacher A | TBD |
| Creative teacher B / comparison | TBD / optional |
| Primary compact student | TBD |
| Larger student challenger | TBD / optional |
| Operational model-assisted oracle | None by default; deterministic preferred |
| WorldTUI-derived checkpoint experiment | TBD / optional |

## Candidate record template

For each considered model record:
- exact model/repository/revision;
- parameter count;
- context;
- tokenizer/chat/tool format;
- license and output/training-use disposition;
- local inference backend;
- structured-output probe result;
- persona/spontaneity probe result;
- secret-discipline probe result;
- runtime memory/latency target measurement;
- fine-tuning method compatibility;
- redistribution/export constraints.

## Selection criteria

The cast should maximize the experiment's information value, not simply benchmark strength.

Prefer candidates that let us test:
- whether eccentric teacher behaviour transfers;
- whether command competence and personality can coexist;
- whether a sub-billion student is sufficient;
- whether additional capacity materially improves multi-turn recovery;
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
