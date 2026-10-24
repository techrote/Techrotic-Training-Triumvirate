# Techrotic Training Triumvirate

A model-agnostic training laboratory for compact, characterful NPC commanders that can use a typed command/communication layer reliably while retaining spontaneous, emergent personality.

The project is organized around a **Triumvirate**:

1. **World Authority** — deterministic simulator/interpreter that owns operational truth, state transitions, command validation, and errors.
2. **Creative Teacher** — one or more pluggable models or generators that contribute personality, unusual language, tactics, riddles, doctrine, and stylistic variation without being allowed to invent authoritative outcomes.
3. **Student Commander** — the compact model trained to consume observations, issue valid commands, recover from failures, preserve secrets, and communicate in character.

The immediate programme is inspired by:
- Simon Edwardsson's WorldTUI training methodology: https://simedw.com/2026/10/21/world-model-terminal/
- Sprocket 500M as an example of a small model with unusually persistent/emergent character behaviour: https://huggingface.co/kandivault/sprocket-500m

Neither Sprocket nor any Qwen/WorldTUI/Liquid/Gemma checkpoint is selected as a required runtime or training model. **The initial model cast is intentionally deferred until the architecture, corpus contracts, and evaluation gates exist.**

## Start here

- [Programme tracker](https://github.com/techrote/Techrotic-Training-Triumvirate/issues/1)
- [Agent execution contract](AGENTS.md)
- [Development workflow](docs/development.md)
- [RAG index](docs/rag/00-index.md)
- [Vision and non-goals](docs/rag/01-vision-and-non-goals.md)
- [Architecture](docs/rag/02-architecture.md)
- [Episode/data contract](docs/rag/03-data-contract.md)
- [Command and console protocol](docs/rag/04-command-and-console.md)
- [Persona and teacher policy](docs/rag/05-persona-and-teacher.md)
- [Evaluation and admission](docs/rag/06-evaluation-and-admission.md)
- [Player intercepts](docs/rag/07-player-intercepts.md)
- [Provenance and reproducibility](docs/rag/08-provenance-reproducibility.md)
- [Implementation programme](docs/rag/09-implementation-programme.md)
- [Planning review](docs/rag/10-planning-review.md)
- [Model-cast admission](docs/rag/11-model-cast-admission.md)
- [Candidate small-model zoo](docs/rag/12-candidate-model-zoo.md)
- [Abstract World Authority](docs/rag/13-world-authority.md)

## Development

The root package is deliberately lightweight: the runtime has no third-party dependencies and supports Python 3.12–3.13.

Install the base project and developer tooling:

```bash
python -m pip install -e ".[dev]"
```

Run the canonical checks:

```bash
python -m pytest
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src
```

Smoke-test the CLI and deterministic seed plumbing:

```bash
ttt --version
ttt seed-demo --seed 24301 --count 5
ttt schema-bundle --pretty
ttt command-schema --pretty
ttt world-demo --seed 24301 --turns 24
```

See [docs/development.md](docs/development.md) for the supported-Python, dependency and artifact-hygiene policy.

## Current status

**Programme Waves 0–3 are complete.**

Merged foundations now include:

- TTT-001 / #2 — reproducible Python package, deterministic tooling and CI;
- TTT-002 / #3 — canonical versioned schemas, T0 fixtures and content hashing;
- TTT-003 / #4 — `ttt-command-v1`, strict typed command parsing and deterministic admission;
- TTT-004 / #5 — framework-neutral deterministic World Authority, replay, delayed execution failures, visibility projections and optional Concordia parity host;
- TTT-006 / #7 — model-agnostic persona mutation and Creative Teacher adapters;
- TTT-007 / #8 — validated deterministic corpus assembly, provenance/license quarantine, deduplication and leak-safe split discipline;
- TTT-008 / #9 — grounded player intercepts, deterministic doctrine/visibility policies and explicit deception broadcasts.

**Wave 4 is in progress.** TTT-007 / #8 is complete; TTT-005 / #6 and TTT-009 / #10 remain ready according to the dependency rules in `docs/rag/09-implementation-programme.md`.

The initial model cast remains deliberately **UNSELECTED**. Model admission stays gated at TTT-011 / issue #12 after corpus, evaluation and corrective-rollout infrastructure is complete.

A first-pass **~20 GB small-model GGUF characterization shelf** is recorded in `docs/rag/12-candidate-model-zoo.md`. It is a shortlist for later benchmarking, not an admission or download authorization.

Architecture decisions now implemented in production code:

- **LangGraph** is the selected orchestration/checkpoint/branch/replay substrate for later session and corrective-rollout work;
- **Concordia** remains an optional richer simulation/Game-Master host, with the native TTT World Authority retained as the canonical dependency-light path.

The native abstract World Authority is available through `ttt world-demo --seed 24301 --turns 24`. Player tactical telegraphs are produced by the grounded `InterceptEncoder` from authoritative dispatch/deception events.

## Core rule

**Never train a student to confuse plausible fiction with authoritative game state.**

Operational labels, command acceptance/rejection, state transitions, and hidden-information boundaries come from deterministic code or explicitly admitted evidence. Creative teachers may propose, phrase, mutate, or dramatize; validators decide what enters the corpus.
