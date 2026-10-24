# Issue-based implementation programme

## Contents

1. Programme principles — sequencing and merge discipline.
2. Current implementation status — completed waves and immediately ready work.
3. Issue map — TTT-001 through TTT-016, GitHub numbers and state.
4. Execution waves — safe parallelism.
5. Dependency graph — explicit blockers.
6. Model-selection gate — where owner choice enters.
7. Expensive-work gate — what must exist before training campaigns.
8. Completion target — what the programme delivers.

Programme tracker: #1.

Architecture spikes:
- SPIKE-LG-001 / #18, implemented by PR #19, proved checkpoint → branch → correction → replay and adopts LangGraph for orchestration/checkpointing while preserving TTT-owned world/event/provenance semantics.
- SPIKE-CD-001 / #20, implemented by PR #21, proved Concordia can host a deterministic non-LLM Game Master with TTT typed-command parsing and separated visibility surfaces. Concordia is conditionally adopted as an optional richer simulation substrate, not the mandatory World Authority.

## 1. Programme principles

Each TTT issue is a merge-sized unit with a self-contained agent prompt. It must follow `AGENTS.md`, read its listed RAG documents, implement, test, open a PR, obtain green automated checks, self-review, and merge.

Issues should be executed from current `main`; agents must reconcile work merged by parallel branches.

## 2. Current implementation status

As of 24 October 2026, **Waves 0–7 are merged**. TTT-012 supplies admitted-model
training/export, and TTT-015's runtime bridge merged through PR #38. TTT-013's
preparation-only issue closed through PR #36; substantive execution is tracked
separately by TTT-013E / #37. Long-session comparison and final admission must
consume that actual evidence rather than substituting smoke output.

| Wave | Issues | State | Result |
|---|---|---|---|
| 0 | TTT-001 / #2 | Complete | Root package, deterministic tooling and base CI |
| 1 | TTT-002 / #3 | Complete | Canonical versioned schemas, T0 fixtures and content hashes |
| 2 | TTT-003 / #4 + TTT-006 / #7 | Complete | Typed command/interpreter layer plus Creative Teacher/persona layer |
| 3 | TTT-004 / #5 + TTT-008 / #9 | Complete | Deterministic World Authority + grounded player-intercept/deception codec |
| 4 | TTT-005 / #6 + TTT-007 / #8 + TTT-009 / #10 | Complete | Session, corpus and frozen model-agnostic evaluation foundation |
| 5 | TTT-010 / #11 | Complete | LangGraph-backed student-visited correction branches and validated T3 recovery corpus |
| 6 | TTT-011 / #12 | Complete | Initial model-cast admission, immutable artifact identities, licensing and live characterization evidence |
| 7 | TTT-012 / #13 + TTT-015 / #16 | Complete | Training/export plus bounded game-facing runtime and intercept bridge |
| 8 | TTT-013 / #14 + TTT-013E / #37 | Preparation merged; real execution in progress | Benchmark-clean local corpus and four-way native LoRA campaign |
| 9 | TTT-014 / #15 | Evaluation implemented; comparison in progress | Frozen 24-turn candidate/baseline traces and human packet |
| 10 | TTT-016 / #17 | Evidence tooling implemented; final package pending | Cards, comparative admission decision and verified readback |

Wave 3 merged evidence:

- TTT-004 / #5: merge `ffdffb4d0f877a1fc04ad308d15d66dbef6f0cdd`; Base CI and `World Concordia parity` both green on the final PR head.
- TTT-008 / #9: merge `a70eb28a39527aeb40b69a2e9543eb54a9212b69`; Base CI green after reconciling onto the merged TTT-004 head.
- The native World Authority remains the canonical dependency-light execution path. Concordia is optional and parity-checked.
- Ordinary player intercepts are grounded in real `command-dispatched` events; false tactical messages require explicit authoritative deception events.

Wave 4 merged evidence:

- TTT-005 / #6: PR #30 implements optional LangGraph-backed session checkpoint/history/replay, deterministic structured/text/delta rendering, hash-verified session recording, and non-mutating historical correction branches.
- TTT-007 / #8: PR #29 implements deterministic T0–T3 corpus assembly, provenance/license quarantine, schema/protocol and leakage validators, exact/near deduplication, family-aware train/dev splits, frozen-evaluation isolation, recovery context and content-addressed JSONL/manifest output.
- TTT-009 / #10: PR #31 implements the frozen generated/adversarial evaluation suite, deterministic StudentAdapter baselines, recovery/leakage metrics and immutable family/seed training guard.

Wave 5 result:

- TTT-010 / #11 adds deterministic scripted/replay students, failure categorization, simulator-oracle repair, historical LangGraph correction forks, branch-preserving T3 recovery examples, multiple alternatives, iterative parent-run lineage and fail-closed frozen-evaluation refusal.

TTT-011 admits identities and characterization only; it does **not** authorize a substantial training campaign. TTT-012 must prove the bounded smoke train/export path before TTT-013 may consume the admitted pilot budget.

## 3. Issue map

| ID | Issue | State | Deliverable |
|---|---:|---|---|
| TTT-001 | #2 | Complete | Repository/package bootstrap, deterministic dev tooling and CI |
| TTT-002 | #3 | Complete | Versioned canonical schemas for scenarios, observations, episodes, provenance |
| TTT-003 | #4 | Complete | Typed command IR, deterministic interpreter, stable error taxonomy |
| TTT-004 | #5 | Complete | Framework-neutral abstract battlefield World Authority, procedural scenarios, and optional Concordia host parity |
| TTT-005 | #6 | Complete | LangGraph-backed session/checkpoint/replay orchestration plus console/delta views |
| TTT-006 | #7 | Complete | Model-agnostic creative-teacher/persona mutation subsystem |
| TTT-007 | #8 | Complete | Corpus assembler, validators, provenance, dedup and split discipline |
| TTT-008 | #9 | Complete | Player intercept/telegraph semantic codec and explicit deception model |
| TTT-009 | #10 | Complete | Evaluation harness, frozen generated/handwritten suites and baselines |
| TTT-010 | #11 | Complete | LangGraph branch/update-state corrective rollout pipeline inspired by DAgger-style repair |
| TTT-011 | #12 | Complete | Initial model-cast admission: owner-delegated teacher/student selection, licensing/runtime probes, frozen decision record |
| TTT-012 | #13 | Complete | Reproducible fine-tuning/export harness for the admitted cast |
| TTT-013 | #14 | Complete under preparation-only rule | Pilot admission and fixed four-way plan |
| TTT-013E | #37 | Real execution in progress | Named local allocation, actual adapters and source-bound evaluation |
| TTT-014 | #15 | Full comparison in progress | Closed-loop 20–30 turn commander benchmark and comparative report |
| TTT-015 | #16 | Complete / PR #38 | Runtime export/bridge contract plus reference intercept integration |
| TTT-016 | #17 | Final evidence pending #37/#15 | Model/data cards, explicit admission/rejection and reproducibility |

## 4. Execution waves

**Wave 0:** TTT-001 / #2.

**Wave 1:** TTT-002 / #3.

**Wave 2, parallel:** TTT-003 / #4 and TTT-006 / #7.

**Wave 3:** TTT-004 / #5 after TTT-003; TTT-008 / #9 can run in parallel after TTT-003.

**Wave 4:** TTT-005 / #6, TTT-007 / #8 and TTT-009 / #10 are complete.

**Wave 5:** TTT-010 / #11 is merged after TTT-007/009.

**Wave 6:** TTT-011 / #12 is merged after the owner explicitly delegated the cast decision to the implementation agent.

**Wave 7, parallel:** TTT-012 / #13 and TTT-015 / #16 are complete.

**Wave 8:** TTT-013 / #14 preparation is complete; TTT-013E / #37 executes the
real fixed campaign under the recorded local allocation and budget.

**Wave 9:** TTT-014 / #15 consumes actual TTT-013E candidates and preserved
prompt-only/scripted controls.

**Wave 10:** TTT-016 / #17 after TTT-014/015.

## 5. Dependency graph

```
001 -> 002
002 -> 003
002 -> 006
003 -> 004
003 -> 008
004 -> 005
002+003+004+006 -> 007
003+004 -> 009
005 -> 009 (consume if merged; do not block early harness scaffolding)
007+009 -> 010
006+007+009+010 -> 011
011 -> 012
011+008+009 -> 015
012 -> 013
013 -> 014
014+015 -> 016
```

## 6. Model-selection gate

TTT-011 / #12 is the authoritative initial selection/admission gate. The owner
explicitly delegated the cast decision to the implementation agent on
24 October 2026, clearing the prior `UNSELECTED` blocker.

The admitted initial roles are:

- **Creative teacher A / creative reference:** Sprocket 500M.
- **Creative teacher B / structured comparison:** Qwen3.5-4B.
- **Primary compact student:** LFM2.5-1.2B-Instruct.
- **Larger challenger student:** Qwen3.5-4B.
- **Operational oracle:** deterministic World Authority; no model-assisted oracle.
- **WorldTUI checkpoint experiment:** none in the initial cast.

The exact native and GGUF identities, SHA-256 values, licensing dispositions,
runtime targets and bounded downstream budgets live in
`11-model-cast-admission.md` and the machine-readable
`src/techrotic_training_triumvirate/model_cast_v1.json`. The earlier
`12-candidate-model-zoo.md` remains characterization/planning history and is
not an independent admission source.

## 7. Expensive-work gate

Before substantial corpus generation or GPU fine-tuning:
- TTT-007 corpus validation/provenance is merged;
- TTT-009 evaluation is merged;
- TTT-011 has immutable model/cost/config identities;
- TTT-012 smoke train/export path passes;
- the executing issue states the admitted budget and stopping conditions.

Default CI remains CPU-small and model-download-free.

## 8. Completion target

Programme completion yields:
- a deterministic synthetic command world;
- persona/teacher generation adapters;
- a validated, provenance-rich corpus pipeline;
- recovery-data generation;
- frozen evaluation suites;
- a compact commander candidate experiment and an explicit evidence-based
  admission, conditional-admission or rejection decision;
- player-facing grounded tactical intercepts;
- reproducible runtime/export artifacts ready for downstream game integration.

A negative research result is a valid TTT-016 completion under issue #17.
It completes the evidence programme without claiming the rejected candidate
is ready for game integration. Original model-cast selection, actual fine-tuned
candidate evidence and final runtime admission are separate decisions.
