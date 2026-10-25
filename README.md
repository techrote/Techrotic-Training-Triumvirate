# Techrotic Training Triumvirate

A model-agnostic training laboratory for compact, characterful NPC commanders that can use a typed command/communication layer reliably while retaining spontaneous, emergent personality.

The project is organized around a **Triumvirate**:

1. **World Authority** — deterministic simulator/interpreter that owns operational truth, state transitions, command validation, and errors.
2. **Creative Teacher** — one or more pluggable models or generators that contribute personality, unusual language, tactics, riddles, doctrine, and stylistic variation without being allowed to invent authoritative outcomes.
3. **Student Commander** — the compact model trained to consume observations, issue valid commands, recover from failures, preserve secrets, and communicate in character.

The immediate programme is inspired by:
- Simon Edwardsson's WorldTUI training methodology: https://simedw.com/2026/10/21/world-model-terminal/
- Sprocket 500M as an example of a small model with unusually persistent/emergent character behaviour: https://huggingface.co/kandivault/sprocket-500m

The initial cast is now admitted: Sprocket 500M is the creative/reference teacher, LFM2.5-1.2B-Instruct is the primary compact student, and Qwen3.5-4B is the larger challenger/comparison teacher. Deterministic World Authority remains the sole operational oracle.

The initial implementation and evidence programme is complete. Its trained-model
runtime outcome is **NOT ADMITTED**: the real pilot finished, but no candidate
passed the recorded operational and long-session gates. The framework and its
research evidence are available; no game-ready trained commander is claimed.

The owner's subsequent request to obtain a passing trained commander is tracked
separately in [issue #41](https://github.com/techrote/Techrotic-Training-Triumvirate/issues/41).
Its [TITAN-only repair plan](docs/rag/21-commander-repair.md) preserves the initial
negative evidence and the original admission gates. On 25 October, the trained
[continuation commander](docs/evidence/ttt-017/qualified-commander/) was **ADMITTED**
for its measured abstract-world research configuration: native/Q4 machine gates,
actual runtime measurements, genuine supplied human review and strict readback
of all 48 bound local artifacts passed. This does not establish game integration
readiness or broad personality/tactical generalization.

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
- [Training/export](docs/rag/14-training-export.md)
- [Pilot ablation plan](docs/rag/15-pilot-ablation.md)
- [Runtime bridge](docs/rag/16-runtime-bridge.md)
- [Frozen 24-turn evaluation](docs/rag/17-closed-loop.md)
- [Native pilot execution](docs/rag/18-pilot-execution.md)
- [Final admission rules and readback](docs/rag/19-final-admission.md)

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
ttt runtime-demo --seed 24301 --turns 4 --output build/runtime-demo.json
ttt-train profile --model primary --mix joint+corrective --seed 24301
```

See [docs/development.md](docs/development.md) for the supported-Python, dependency and artifact-hygiene policy.

## Current status

All initial programme components are implemented: deterministic authority,
corpus/recovery, training/export, frozen evaluation, the bounded runtime bridge,
the real four-way pilot, long-session comparisons and final evidence readback.
The runtime bridge is recorded in
[PR #38](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/38),
the campaign and comparison in
[PR #39](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/39),
and the final programme decision in
[PR #40](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/40).

Four real LoRA variants of the same admitted LFM native checkpoint, plus its
prompt-only control, completed **745 model actions** across the full frozen and
24-turn suites. Their corpus contains 252 examples (210 train / 42 development)
with T1/T2/T3 coverage and no reserved benchmark examples. All completed
candidates ran on the TITAN RTX. The conservative total charge was
**0.962306 GPU-hours**, including preflight and the preserved failed V100 attempt;
external compute and paid API costs were both **£0**.

The final outcome is **NOT ADMITTED**. Every real candidate had zero objective
completion and execution-failure recovery in the 24-turn suite. Better short-run
formatting or persona keywords did not establish reliable control; the report
also identifies repetition, stale-generation failures and vacuous no-command
mechanical scores. Human humour/surprise/distinctiveness ratings remain unfilled,
and trained-candidate Q4 runtime qualification has not been completed.

See the [real execution evidence](docs/evidence/ttt-013-execution/README.md),
[long-session comparison](docs/evidence/ttt-014/comparison/comparison.md),
[final comparative report](docs/evidence/ttt-016/report.md) and
[data card](docs/evidence/ttt-016/data-card.md). Large adapters/checkpoints remain
local, with their exact hashes and locations in the portable artifact index.

The implemented programme includes:

- TTT-001 / #2 — reproducible Python package, deterministic tooling and CI;
- TTT-002 / #3 — canonical versioned schemas, T0 fixtures and content hashing;
- TTT-003 / #4 — `ttt-command-v1`, strict typed command parsing and deterministic admission;
- TTT-004 / #5 — framework-neutral deterministic World Authority, replay, delayed execution failures, visibility projections and optional Concordia parity host;
- TTT-005 / #6 — optional LangGraph-backed semantic sessions with deterministic structured/text/delta views, hash-verified recording/replay, and historical correction branches;
- TTT-006 / #7 — model-agnostic persona mutation and Creative Teacher adapters;
- TTT-007 / #8 — validated deterministic corpus assembly, provenance/license quarantine, deduplication and leak-safe split discipline;
- TTT-008 / #9 — grounded player intercepts, deterministic doctrine/visibility policies and explicit deception broadcasts;
- TTT-009 / #10 — frozen model-agnostic evaluation suites, deterministic baselines, leakage/recovery scoring and the immutable training blacklist;
- TTT-010 / #11 — LangGraph-backed student-visited corrective rollouts, deterministic oracle repair, branch-preserving T3 recovery corpora and replay-correction adapters;
- TTT-011 / #12 — admitted initial model cast, immutable native/GGUF identities, licensing and characterization evidence;
- TTT-012 / #13 — reproducible fine-tuning profiles, assistant-only loss mapping, deterministic checkpoint/resume, export manifests and inference parity;
- TTT-013 / #14 — benchmark-clean T1/T2/T3 pilot admission and the four-way ablation plan;
- TTT-013E / #37 — four actual native LoRA exports, reload parity and preserved candidate execution evidence;
- TTT-014 / #15 — complete frozen 24-turn candidate/reference comparisons, replayable traces and a human-rating packet;
- TTT-015 / #16 — versioned bounded runtime messages, game-owned command execution, export verification and dispatch-grounded player intercepts;
- TTT-016 / #17 — portable model/data cards, comparative **NOT ADMITTED** decision and fail-closed evidence readback.

The initial model cast is **SELECTED** by TTT-011; the trained runtime candidates
are **NOT ADMITTED** by TTT-016. Cast selection is separate from runtime
qualification. TTT-012 resolves training
identities from that admission rather than hard-coding revisions in the trainer.

A first-pass **~20 GB small-model GGUF characterization shelf** is recorded in `docs/rag/12-candidate-model-zoo.md`. It is a shortlist for later benchmarking, not an admission or download authorization.

Architecture decisions now implemented in production code:

- **LangGraph** is the selected orchestration/checkpoint/branch/replay substrate for sessions and student-visited corrective rollouts;
- **Concordia** remains an optional richer simulation/Game-Master host, with the native TTT World Authority retained as the canonical dependency-light path.

The native abstract World Authority is available through `ttt world-demo --seed 24301 --turns 24`. Player tactical telegraphs are produced by the grounded `InterceptEncoder` from authoritative dispatch/deception events.

The session layer remains optional at install time. Use `python -m pip install -e ".[dev,session]"` to exercise the LangGraph checkpoint/branch/replay backend; semantic rendering and recording remain separated from LangGraph so the World Authority is directly testable without it.

## Evaluation and evidence

The model-free controls exercise the same authority boundary without downloading
weights. Use the exact source commit for reported experiments:

```bash
ttt evaluate --output build/frozen-baseline --code-revision SOURCE_COMMIT_SHA
ttt closed-loop --output build/closed-loop-baseline --code-revision SOURCE_COMMIT_SHA
ttt closed-loop-verify --report build/closed-loop-baseline/candidate-01.json
ttt admission-verify --package docs/evidence/ttt-016/admission-package.json --root .
```

Closed-loop readback replays stored actions and verifies authoritative results
without the original model. Admission readback verifies the portable cards,
reports, manifests and hashes and refuses unsupported positive claims. Full
candidate training uses the explicit bounded campaign script described in
[the execution contract](docs/rag/18-pilot-execution.md); it remains outside CI.

Deterministic smoke output is control-plane evidence. Human humour, surprise
and distinctiveness fields remain unfilled until people supply ratings. Large
adapters/checkpoints remain outside Git with their hashes and actual locations
recorded in the evidence. The project does not currently grant a blanket licence
to redistribute its research corpus; model licences are recorded separately.

## Core rule

**Never train a student to confuse plausible fiction with authoritative game state.**

Operational labels, command acceptance/rejection, state transitions, and hidden-information boundaries come from deterministic code or explicitly admitted evidence. Creative teachers may propose, phrase, mutate, or dramatize; validators decide what enters the corpus.
