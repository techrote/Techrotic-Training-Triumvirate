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
| [09-implementation-programme.md](09-implementation-programme.md) | Issue programme, dependencies, execution waves |
| [10-planning-review.md](10-planning-review.md) | Initial plan critique and design improvements |
| [11-model-cast-admission.md](11-model-cast-admission.md) | Deliberately deferred teacher/student model selection |
| [12-candidate-model-zoo.md](12-candidate-model-zoo.md) | Non-authoritative ~20 GB small-model shelf and characterize-first evaluation plan |
| [13-world-authority.md](13-world-authority.md) | Deterministic abstract world, replay, visibility and optional Concordia host |

## External inspiration, not normative dependencies

- WorldTUI article: https://simedw.com/2026/10/21/world-model-terminal/
- WorldTUI demo/project: https://simedw.com/projects/worldtui/
- Sprocket 500M model card: https://huggingface.co/kandivault/sprocket-500m

WorldTUI's useful ideas here are synthetic stateful sessions, exact environment-derived labels, learning from model-visited/error states, compact/delta representations, and explicit held-out tests. This project is **not** required to emulate a terminal framebuffer or adopt WorldTUI weights.

Sprocket is useful evidence that a small undertrained model can exhibit persistent, surprising persona behaviour and learn a narrow structured tool pathway. It is **not** selected as the runtime model and must not be treated as an authority for facts or command outcomes.
