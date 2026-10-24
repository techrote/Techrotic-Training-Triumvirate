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

As of 24 October 2026, **Waves 0–3 are complete and Wave 4 is in progress**.

| Wave | Issues | State | Result |
|---|---|---|---|
| 0 | TTT-001 / #2 | Complete | Root package, deterministic tooling and base CI |
| 1 | TTT-002 / #3 | Complete | Canonical versioned schemas, T0 fixtures and content hashes |
| 2 | TTT-003 / #4 + TTT-006 / #7 | Complete | Typed command/interpreter layer plus Creative Teacher/persona layer |
| 3 | TTT-004 / #5 + TTT-008 / #9 | Complete | Deterministic World Authority + grounded player-intercept/deception codec |
| 4 | TTT-005 / #6 + TTT-007 / #8 + TTT-009 / #10 | **In progress** | TTT-007 complete; TTT-005 and TTT-009 remain ready |

Wave 3 merged evidence:

- TTT-004 / #5: merge `ffdffb4d0f877a1fc04ad308d15d66dbef6f0cdd`; Base CI and `World Concordia parity` both green on the final PR head.
- TTT-008 / #9: merge `a70eb28a39527aeb40b69a2e9543eb54a9212b69`; Base CI green after reconciling onto the merged TTT-004 head.
- The native World Authority remains the canonical dependency-light execution path. Concordia is optional and parity-checked.
- Ordinary player intercepts are grounded in real `command-dispatched` events; false tactical messages require explicit authoritative deception events.

Wave 4 progress:

- TTT-007 / #8: PR #29 implements deterministic T0–T3 corpus assembly, provenance/license quarantine, schema/protocol and leakage validators, exact/near deduplication, family-aware train/dev splits, frozen-evaluation isolation, recovery context and content-addressed JSONL/manifest output.

Do not start model-specific training merely because the model zoo exists. TTT-011 remains downstream of TTT-007, TTT-009 and TTT-010.

## 3. Issue map

| ID | Issue | State | Deliverable |
|---|---:|---|---|
| TTT-001 | #2 | Complete | Repository/package bootstrap, deterministic dev tooling and CI |
| TTT-002 | #3 | Complete | Versioned canonical schemas for scenarios, observations, episodes, provenance |
| TTT-003 | #4 | Complete | Typed command IR, deterministic interpreter, stable error taxonomy |
| TTT-004 | #5 | Complete | Framework-neutral abstract battlefield World Authority, procedural scenarios, and optional Concordia host parity |
| TTT-005 | #6 | Ready | LangGraph-backed session/checkpoint/replay orchestration plus console/delta views |
| TTT-006 | #7 | Complete | Model-agnostic creative-teacher/persona mutation subsystem |
| TTT-007 | #8 | Complete | Corpus assembler, validators, provenance, dedup and split discipline |
| TTT-008 | #9 | Complete | Player intercept/telegraph semantic codec and explicit deception model |
| TTT-009 | #10 | Ready | Evaluation harness, frozen generated/handwritten suites and baselines |
| TTT-010 | #11 | Blocked by #10 | LangGraph branch/update-state corrective rollout pipeline inspired by DAgger-style repair |
| TTT-011 | #12 | Blocked / model cast unselected | Initial model-cast admission: owner-selected teacher/student candidates, licensing/runtime probes, frozen decision record |
| TTT-012 | #13 | Blocked by #12 | Reproducible fine-tuning/export harness for the admitted cast |
| TTT-013 | #14 | Blocked by #13 | Pilot corpus generation and smoke/ablation fine-tunes |
| TTT-014 | #15 | Blocked by #14 | Closed-loop 20–30 turn commander benchmark and comparative report |
| TTT-015 | #16 | Blocked by #10/#12 | Runtime export/bridge contract plus reference intercept integration |
| TTT-016 | #17 | Blocked by #15/#16 | Release/admission package: model/data cards, manifests, benchmarks and reproducibility |

## 4. Execution waves

**Wave 0:** TTT-001 / #2.

**Wave 1:** TTT-002 / #3.

**Wave 2, parallel:** TTT-003 / #4 and TTT-006 / #7.

**Wave 3:** TTT-004 / #5 after TTT-003; TTT-008 / #9 can run in parallel after TTT-003.

**Wave 4, parallel where practical:** TTT-005 / #6 after TTT-004; TTT-007 / #8 after TTT-002/003/004/006; TTT-009 / #10 after TTT-003/004 and may consume TTT-005 when available.

**Wave 5:** TTT-010 / #11 after TTT-007/009.

**Wave 6:** TTT-011 / #12 after TTT-006/007/009/010. This is the deliberate model-selection gate.

**Wave 7, parallel:** TTT-012 / #13 and TTT-015 / #16 after TTT-011 (TTT-015 also requires TTT-008/009).

**Wave 8:** TTT-013 / #14 after TTT-012.

**Wave 9:** TTT-014 / #15 after TTT-013.

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

No teacher/student lineup is selected in this programme document.

A non-authoritative first-pass ~20 GB small-model characterization shelf is recorded in `12-candidate-model-zoo.md`. It exists to make TTT-011 evidence-driven and **must not be interpreted as admission or download authorization**.

TTT-011 / #12 is blocked until the owner records the initial cast decision in `11-model-cast-admission.md` or its issue. Candidate analysis may precede the final decision, but implementation must not silently choose a checkpoint.

Possible roles to fill:
- creative teacher(s);
- operational/oracle teacher if model-assisted;
- primary compact student;
- larger comparison student;
- optional WorldTUI-derived/terminal-model experiment.

A role may be "none/deterministic" where appropriate.

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
- an admitted compact commander candidate;
- player-facing grounded tactical intercepts;
- reproducible runtime/export artifacts ready for downstream game integration.
