# RAG index

This directory is the authoritative compact context pack for implementation agents.

## Reading rule

Always read `AGENTS.md` first. Then read the issue's **Required reading** list. Use [`../development.md`](../development.md) for the canonical install/test/lint/type commands. When in doubt, prefer the current documents in this directory over assumptions embedded in an old issue body.

## Documents

| Document | Purpose |
|---|---|
| [01-vision-and-non-goals.md](01-vision-and-non-goals.md) | Product intent, core experiment, boundaries |
| [02-architecture.md](02-architecture.md) | Triumvirate architecture, trust boundaries, component flow |
| [03-data-contract.md](03-data-contract.md) | Canonical state/episode/corpus concepts and leakage boundaries |
| [04-command-and-console.md](04-command-and-console.md) | Typed command IR, deterministic interpreter, console/session surface |
| [05-persona-and-teacher.md](05-persona-and-teacher.md) | Creative teacher responsibilities, persona mutation, validation |
| [06-evaluation-and-admission.md](06-evaluation-and-admission.md) | Metrics, frozen tests, model/run admission gates |
| [07-player-intercepts.md](07-player-intercepts.md) | Encoded tactical telegraphing and explicit deception |
| [08-provenance-reproducibility.md](08-provenance-reproducibility.md) | Seeds, manifests, hashes, licensing and run evidence |
| [09-implementation-programme.md](09-implementation-programme.md) | Completed issue programme, dependencies, execution waves and negative final outcome |
| [10-planning-review.md](10-planning-review.md) | Initial plan critique and design improvements |
| [11-model-cast-admission.md](11-model-cast-admission.md) | Selected teacher/student cast, immutable identities, licensing and runtime evidence |
| [12-candidate-model-zoo.md](12-candidate-model-zoo.md) | Non-authoritative ~20 GB small-model shelf and characterize-first evaluation plan |
| [13-world-authority.md](13-world-authority.md) | Deterministic abstract world, replay, visibility and optional Concordia host |
| [14-training-export.md](14-training-export.md) | Reproducible fine-tuning, checkpoint/resume, export, parity and budget gates |
| [15-pilot-ablation.md](15-pilot-ablation.md) | Pilot admission, four-way plan, preparation history and actual-execution links |
| [16-runtime-bridge.md](16-runtime-bridge.md) | Bounded versioned game/model bridge, identity, authority and grounded intercepts |
| [17-closed-loop.md](17-closed-loop.md) | Frozen 24-turn evaluation, separated metrics, trace replay and blinded human packet |
| [18-pilot-execution.md](18-pilot-execution.md) | Completed local native pilot, corpus, budgets, device identity and source provenance |
| [19-final-admission.md](19-final-admission.md) | Prospective admission gates, model/data cards and fail-closed evidence readback |
| [20-commander-repair.md](20-commander-repair.md) | TITAN-only continuation toward a trained commander passing the unchanged gates |

## Initial programme outcome

The initial implementation and evidence programme is complete, including the
real four-way native pilot and prompt-only control through
[PR #39](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/39) and
the final decision through
[PR #40](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/40).
The outcome is **NOT ADMITTED**. All five real candidates completed their frozen
and 24-turn evaluations (745 model actions); none passed the long-session
objective/recovery gates. Human ratings remain unfilled and trained Q4 runtime
qualification is not claimed.

Start with the [execution evidence](../evidence/ttt-013-execution/README.md),
[comparative report](../evidence/ttt-016/report.md) and
[admission package](../evidence/ttt-016/admission-package.json). Document 15 retains
the original preparation-only history; document 18 describes the actual
execution and its provenance. Successful implementation and a negative model
admission decision are separate conclusions.

## External inspiration, not normative dependencies

- WorldTUI article: https://simedw.com/2026/10/21/world-model-terminal/
- WorldTUI demo/project: https://simedw.com/projects/worldtui/
- Sprocket 500M model card: https://huggingface.co/kandivault/sprocket-500m

WorldTUI's useful ideas here are synthetic stateful sessions, exact environment-derived labels, learning from model-visited/error states, compact/delta representations, and explicit held-out tests. This project is **not** required to emulate a terminal framebuffer or adopt WorldTUI weights.

Sprocket is now admitted as a creative/reference teacher only. It remains untrusted model output and must never be treated as an authority for facts, command success, or world outcomes.
