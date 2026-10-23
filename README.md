# Techrotic Training Triumvirate

A model-agnostic training laboratory for compact, characterful NPC commanders that can use a typed command/communication layer reliably while retaining spontaneous, emergent personality.

The project is organized around a **Triumvirate**:

1. **World Authority** — deterministic simulator/interpreter that owns operational truth, state transitions, command validation, and errors.
2. **Creative Teacher** — one or more pluggable models or generators that contribute personality, unusual language, tactics, riddles, doctrine, and stylistic variation without being allowed to invent authoritative outcomes.
3. **Student Commander** — the compact model trained to consume observations, issue valid commands, recover from failures, preserve secrets, and communicate in character.

The immediate programme is inspired by:
- Simon Edwardsson's WorldTUI training methodology: https://simedw.com/2026/10/21/world-model-terminal/
- Sprocket 500M as an example of a small model with unusually persistent/emergent character behaviour: https://huggingface.co/kandivault/sprocket-500m

Neither Sprocket nor any Qwen/WorldTUI checkpoint is selected as a required runtime or training model. **The initial model cast is intentionally deferred until the architecture, corpus contracts, and evaluation gates exist.**

## Start here

- [Programme tracker](https://github.com/techrote/Techrotic-Training-Triumvirate/issues/1)
- [Agent execution contract](AGENTS.md)
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

## Current status

The reviewed programme and RAG context are published. **TTT-001 / issue #2 is ready to execute.** The implementation queue runs through TTT-016 / issue #17.

The initial model cast remains deliberately **UNSELECTED** and is admitted only at TTT-011 / issue #12 after the model-independent command, corpus, recovery, and evaluation foundations exist.

Each implementation issue contains an autonomous-agent prompt and inherits the repository-wide requirement to implement, test, open a focused PR, satisfy automated checks, self-review, and merge.

## Core rule

**Never train a student to confuse plausible fiction with authoritative game state.**

Operational labels, command acceptance/rejection, state transitions, and hidden-information boundaries come from deterministic code or explicitly admitted evidence. Creative teachers may propose, phrase, mutate, or dramatize; validators decide what enters the corpus.
