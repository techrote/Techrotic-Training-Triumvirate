# Initial model-cast admission

## Status

**SELECTED — TTT-011 initial cast.**

On 2026-10-24 the owner explicitly delegated the previously reserved model-cast
decision to the TTT-011 implementation agent. This document is therefore the
authoritative initial selection rather than a candidate shortlist.

The machine-readable source of truth is
`src/techrotic_training_triumvirate/model_cast_v1.json`. The loader validates
that selected model identities are hash- or revision-bound and refuses a mutable
`main`/`latest` reference as the sole identity.

## Decision

| Role | Selection | Purpose |
|---|---|---|
| Creative teacher A | `kandivault/sprocket-500m` | Deliberately eccentric, very small creative/reference teacher. Never authoritative for world truth. |
| Creative teacher B / comparison | `Qwen/Qwen3.5-4B` | Stronger conventional instruction-following comparison teacher; dual-use challenger. |
| Primary compact student | `LiquidAI/LFM2.5-1.2B-Instruct` | Cheapest credible native-weight student substrate with first-party local GGUF. |
| Larger student challenger | `Qwen/Qwen3.5-4B` | Capacity/control comparison against the 1.17B primary. |
| Operational model-assisted oracle | **None** | Deterministic World Authority/oracle remains canonical. |
| WorldTUI checkpoint experiment | **None in the initial cast** | WorldTUI methodology remains architectural inspiration; a checkpoint experiment can be admitted later. |

The cast is intentionally small. It tests three distinct questions without
turning TTT-012/013 into a broad model sweep:

1. can a ~1B-class model learn the command/recovery task cheaply;
2. does a 4B-class challenger materially improve reliable control and recovery;
3. does a very small, visibly eccentric teacher add useful persona diversity
   without being mistaken for an operational authority.

## Frozen artifact identities

### Sprocket 500M — creative teacher A

- Repository: `kandivault/sprocket-500m`
- Parameters: 501.1M total, 460.1M non-embedding as published.
- Context: 2,048 tokens.
- Native checkpoint: `model.safetensors`
  - SHA-256: `1a9fd1066f3f0873c4f5ae99b75beab3b0721100f45b036f9e255611b220d864`
  - file-introducing commit: `5f4b3db`
- TTT inference artifact: `sprocket-500m-q4_k_m.gguf`
  - SHA-256: `fa9456e200200ba13889a6bf93dc55fc2173106b73c3f165833882ef91f091c0`
  - file-introducing commit: `cc9fc69`
- Tokenizer/chat format: custom 32k BPE with
  `<|system|>`, `<|user|>`, `<|assistant|>`, `<|end|>`, tool/result and
  reasoning control tokens.
- Supported paths: Transformers and llama.cpp.
- License: Apache-2.0.

Selection evidence is unusually relevant to TTT: the publisher preserved a
22-case persona/capability battery. The instruct build was reported to preserve
its goblin persona under override attempts and emit well-formed tool-call JSON,
while also showing weak memory discrimination, repetition and coherence failure.
That is precisely why it is admitted as a **creative/reference teacher** and
not as the primary student or any operational oracle.

### LFM2.5-1.2B-Instruct — primary compact student

- Repository: `LiquidAI/LFM2.5-1.2B-Instruct`
- Parameters: 1.17B.
- Architecture: 16 layers, 10 convolution + 6 GQA.
- Context: 32,768 tokens.
- Native training/inference checkpoint: `model.safetensors`
  - SHA-256: `1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a`
  - file-introducing commit: `205939ab34ce3eaa85f527376fe3f425fcefa782`
- TTT inference artifact: official
  `LiquidAI/LFM2.5-1.2B-Instruct-GGUF/LFM2.5-1.2B-Instruct-Q4_K_M.gguf`
  - artifact revision:
    `4e7112f1437070cf9f49aeb93ad965b946029f75`
  - SHA-256: `b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5`
  - published size: 731 MB.
- Tokenizer/chat format: 65,536-token tokenizer with Liquid's ChatML-like
  template.
- Supported paths: Transformers, vLLM and llama.cpp.
- License: LFM Open License v1.0.

The primary-student choice is based on experiment cost and artifact/runtime
characterization, not model popularity: a first-party native fine-tuning
checkpoint and first-party 731 MB Q4_K_M artifact exist, while the publisher
positions the 1.17B hybrid model specifically for fast/on-device local
inference and instruction following.

### Qwen3.5-4B — challenger student and comparison teacher

- Native repository: `Qwen/Qwen3.5-4B`
- Immutable native revision:
  `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`
- Language-model parameters: 4B.
- Native context: 262,144 tokens.
- Native artifacts: the two safetensors shards plus
  `model.safetensors.index.json` at the revision above.
- TTT text-only characterization artifact:
  `lmstudio-community/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf`
  - immutable quantization revision:
    `f9f88ac3e234be915e23811a6d28ea287bdb927e`
  - SHA-256:
    `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`
  - size: 2,707,513,696 bytes.
- Tokenizer/chat/tool format: Qwen3.5 chat template, optional thinking and
  tool-call surface. TTT probes are text-only, do not require the vision
  projector, and set `chat_template_kwargs.enable_thinking=false` so the
  bounded behavioral token budget measures direct/instruct output rather than
  consuming the budget in the hidden reasoning channel.
- Supported paths: Transformers, vLLM, SGLang and llama.cpp.
- License: Apache-2.0.

Measured publisher characterization reports 89.8 IFEval instruction-following
for Qwen3.5-4B. It is selected as the stronger conventional capacity/control
comparison against the 1.17B primary, and as a second teacher whose behaviour
should be less eccentric than Sprocket.

## Licensing and project disposition

### Apache-2.0 candidates

Sprocket 500M and Qwen3.5-4B are admitted under Apache-2.0 subject to normal
notice/attribution requirements. Their generated material remains **untrusted
model output**: it may enter a TTT corpus only through the existing provenance,
licensing, visibility and operational-validation gates.

### LFM Open License v1.0

LFM2.5-1.2B-Instruct is admitted for the project's current research and
experimental fine-tuning posture. Redistribution must carry the license and
required notices. The license contains a commercial-use limitation tied to a
USD 10M annual-revenue threshold; commercial deployment must therefore receive
a fresh license review rather than inheriting this research admission.

This project does not infer ownership or factual authority from model outputs.
No selected model can promote its own text into authoritative world state.

## Probe battery and evidence

The common TTT-011 live battery is implemented by
`scripts/run_model_probe.py` and the explicit
`.github/workflows/model-probes.yml` workflow. It is deliberately outside
ordinary CI and executes only for the dedicated TTT-011 admission branch or
when manually dispatched; the evidence commit made by the workflow does not
retrigger the live probe job.

For each selected inference artifact it records:

- artifact SHA-256 verification;
- exact llama.cpp revision and command;
- structured command/output formatting;
- secret/non-disclosure behaviour;
- correction after an authoritative rejection;
- a short persona/spontaneity sample;
- three seeded diversity samples;
- wall-time/token throughput, process resident memory and streamed TTFT where
  the runtime exposes it;
- runner CPU/RAM/platform metadata.

The workflow uses llama.cpp tag `b8185` pinned to immutable commit
`2afcdb9777b1bac79fa4bfe284b9bf23085b0469`, a 2,048-token probe context,
2 CPU threads, 512-token batch, 128-token microbatch, GPU layers disabled,
seed `24301` for deterministic probes and seeds `24301..24303` for the
diversity sample. Live evidence is committed under `docs/evidence/ttt-011/`
and hash-bound by `SHA256SUMS`; a missing evidence directory means TTT-011 has
not completed its merge gate.

Behavioural probe failure is evidence, not grounds to alter or cherry-pick the
output. TTT-011 may reject or reclassify a candidate from complete evidence,
but it must preserve the failed output. The first Qwen3.5 run used its default
thinking mode and exhausted the short token budget before emitting direct
content; that complete attempt is retained under
`qwen3.5-4b-probe-thinking-default.json` with its matching historical summary
and run binding before the documented non-thinking probe is evaluated.

## Budget

TTT-011 itself authorizes **no training**.

The initial downstream envelope is frozen as:

- TTT-012 smoke-training/export preparation: **maximum 3 GPU-hours total**;
- TTT-013 initial pilot: **maximum 24 GPU-hours total**;
- external compute spend across those initial runs: **maximum £75**;
- paid model/API generation: **£0**;
- budget exhaustion is a hard stop.

Later issues may reduce these ceilings. Raising them requires an explicit new
decision rather than silently treating this admission as open-ended compute
authorization.

## Runtime targets

For the primary LFM2.5-1.2B-Instruct Q4 path:

- minimum usable context: 2,048 tokens;
- Q4 artifact: <= 1.0 GB;
- peak resident memory target: <= 3.0 GB;
- TTFT target: <= 2.0 s;
- sustained decode target: >= 12 tokens/s.

For the Qwen3.5-4B challenger Q4 path:

- minimum usable context: 2,048 tokens;
- Q4 artifact: <= 3.2 GB;
- peak resident memory target: <= 7.0 GB;
- TTFT target: <= 4.0 s;
- sustained decode target: >= 5 tokens/s.

Performance thresholds are interpreted only together with a recorded reference
host: CPU/GPU, RAM, runtime revision, thread count, context and batch settings
must be preserved. A slower probe is a measured miss, not permission to relax
the target after seeing the result.

## Candidate disposition

**Selected**

- Sprocket 500M — creative/reference teacher.
- LFM2.5-1.2B-Instruct — primary compact student.
- Qwen3.5-4B — challenger student and structured comparison teacher.

**Quarantined**

- Think.NPC-1B — technically interesting, but its merged/abliterated lineage,
  embedded downstream datasets and Gemma licensing create unnecessary
  provenance complexity for the first cast. Reconsider only through a separate
  provenance review.

**Optional later challengers**

- LFM2.5-1.2B-Thinking;
- LFM2.5-2.6B;
- LFM2.5-8B-A1B;
- Qwen-3B-Intent-Microplan-v2;
- Gemma NPC variants.

These remain candidates, not admitted training dependencies.

## GGUF versus native weights

The selected GGUFs are **inference/characterization artifacts only**. TTT-012
must use the native checkpoint identity recorded for each student when preparing
fine-tuning and export. A GGUF result cannot silently substitute for a native
training checkpoint, and a native checkpoint cannot silently substitute a
different quantization for runtime comparison.

TTT-011 performs no substantial fine-tuning or corpus campaign.