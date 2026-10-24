# Issue-based implementation programme

## Contents

1. Programme principles — sequencing and merge discipline.
2. Issue map — TTT-001 through TTT-016 and GitHub numbers.
3. Execution waves — safe parallelism.
4. Dependency graph — explicit blockers.
5. Model-selection gate — where owner choice enters.
6. Expensive-work gate — what must exist before training campaigns.
7. Completion target — what the programme delivers.

Programme tracker: #1.

## 1. Programme principles

Each TTT issue is a merge-sized unit with a self-contained agent prompt. It must follow `AGENTS.md`, read its listed RAG documents, implement, test, open a PR, obtain green automated checks, self-review, and merge.

Issues should be executed from current `main`; agents must reconcile work merged by parallel branches.

## 2. Issue map

| ID | Issue | Deliverable |
|---|---:|---|
| TTT-001 | #2 | Repository/package bootstrap, deterministic dev tooling and CI |
| TTT-002 | #3 | Versioned canonical schemas for scenarios, observations, episodes, provenance |
| TTT-003 | #4 | Typed command IR, deterministic interpreter, stable error taxonomy |
| TTT-004 | #5 | Abstract battlefield simulator and procedural scenario generator |
| TTT-005 | #6 | Stateful console/session renderer, recorder, replay and delta views |
| TTT-006 | #7 | Model-agnostic creative-teacher/persona mutation subsystem |
| TTT-007 | #8 | Corpus assembler, validators, provenance, dedup and split discipline |
| TTT-008 | #9 | Player intercept/telegraph semantic codec and explicit deception model |
| TTT-009 | #10 | Evaluation harness, frozen generated/handwritten suites and baselines |
| TTT-010 | #11 | Student-visited/corrective rollout pipeline inspired by DAgger-style repair |
| TTT-011 | #12 | Initial model-cast admission: owner-selected teacher/student candidates, licensing/runtime probes, frozen decision record |
| TTT-012 | #13 | Reproducible fine-tuning/export harness for the admitted cast |
| TTT-013 | #14 | Pilot corpus generation and smoke/ablation fine-tunes |
| TTT-014 | #15 | Closed-loop 20–30 turn commander benchmark and comparative report |
| TTT-015 | #16 | Runtime export/bridge contract plus reference intercept integration |
| TTT-016 | #17 | Release/admission package: model/data cards, manifests, benchmarks and reproducibility |

## 3. Execution waves

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

## 4. Dependency graph

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

## 5. Model-selection gate

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

## 6. Expensive-work gate

Before substantial corpus generation or GPU fine-tuning:
- TTT-007 corpus validation/provenance is merged;
- TTT-009 evaluation is merged;
- TTT-011 has immutable model/cost/config identities;
- TTT-012 smoke train/export path passes;
- the executing issue states the admitted budget and stopping conditions.

Default CI remains CPU-small and model-download-free.

## 7. Completion target

Programme completion yields:
- a deterministic synthetic command world;
- persona/teacher generation adapters;
- a validated, provenance-rich corpus pipeline;
- recovery-data generation;
- frozen evaluation suites;
- an admitted compact commander candidate;
- player-facing grounded tactical intercepts;
- reproducible runtime/export artifacts ready for downstream game integration.
