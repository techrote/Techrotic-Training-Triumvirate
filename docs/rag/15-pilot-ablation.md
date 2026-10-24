# TTT-013 pilot corpus and ablation campaign

## Purpose

TTT-013 is the first controlled comparison of operational-only, persona-only,
joint operational+persona, and joint+corrective/T3 supervision on one admitted
student checkpoint.

The substantive campaign must use the same immutable base checkpoint, compatible
training profile, seed/evaluation settings, and a content-addressed pilot corpus
that contains representative T1, T2, and T3 examples while containing **zero**
TTT-009 frozen-evaluation examples.

## Pilot corpus admission

`validate_pilot_manifest()` and `build_pilot_plan()` fail closed unless:

- T1, T2, and T3 are all represented;
- the TTT-007 manifest is readable and shard hashes verify through the TTT-012
  corpus loader;
- `frozen_eval` contains zero examples and no non-empty frozen shard exists;
- the corpus is bound to the current TTT-009 benchmark guard identity.

The resulting plan records corpus counts, tier/split composition, teacher
contribution, rejection/error statistics, exact dataset identity, benchmark
identity, and four resolved training variants.

## Four variants

The initial matrix is deliberately fixed:

1. `operational`
2. `persona`
3. `joint`
4. `joint+corrective`

All four resolve the same admitted student and native checkpoint and use the
same training seed/profile except for the dataset mix. The requested TTT-013
budget is split evenly as a per-variant cap so the comparison remains bounded;
unused capacity is not automatically transferable into an unrecorded extra run.

## Budget

TTT-011 admits the following hard ceiling for this issue:

- 24 GPU-hours total;
- £75 external compute total across the initial TTT-012/013 envelope;
- £0 paid model/API generation.

`authorize_pilot_budget()` enforces the TTT-013 GPU ceiling separately from the
smaller TTT-012 smoke-training ceiling. Budget admission is necessary but is not
itself a compute allocation.

## Execution state at TTT-013 preparation merge

No repository document or workflow currently names an admitted TTT-013 GPU host
or allocation identifier. Therefore the substantive LFM2.5-1.2B-Instruct
four-way fine-tune campaign is **not executed or claimed** by this preparation
merge.

This is the explicit stopping condition required by issue #14: a recorded
budget ceiling exists, but an execution allocation does not. A later operator
may prepare the exact campaign with:

```bash
ttt-train pilot-plan \
  --corpus artifacts/pilot-corpus-v1 \
  --output artifacts/ttt-013-plan.json \
  --model primary \
  --seed 24301 \
  --gpu-hours 24 \
  --external-cost-gbp 75
```

Once an admitted host/allocation is recorded, the plan can be regenerated with
`--execution-host` and `--allocation-id`. Actual heavyweight training remains
an explicit opt-in invocation; the plan does not spend the budget.

## Deterministic smoke comparison

`ttt-train pilot-smoke` runs all four mixes through TTT-012's
`tiny-deterministic-v1` backend, checkpoint/export path, and reload parity
checks:

```bash
ttt-train pilot-smoke \
  --output build/ttt-013-smoke \
  --model primary \
  --seed 24301 \
  --git-commit "$(git rev-parse HEAD)"
```

The emitted `smoke-comparison.json` explicitly sets
`quality_evidence=false` and `substantive_campaign_executed=false`. It proves
control-plane orchestration only and must never be described as LFM/Qwen model
quality evidence.

## Evaluation and reporting contract

Every **real** candidate produced by the eventual substantive campaign must run
the frozen TTT-009 benchmark. Mechanical/closed-loop/hidden-information metrics
remain separate from persona/repetition/diversity proxies. Catastrophic style
collapse, repetition, and command regression must be called out explicitly.

Training loss, export parity, or the deterministic smoke backend cannot by
themselves promote a candidate to runtime.
