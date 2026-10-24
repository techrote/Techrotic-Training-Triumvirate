# TTT-013E real native pilot execution

All five candidates completed: the admitted native LFM primary checkpoint
without an adapter, plus operational, persona, joint, and joint+corrective LoRA
variants. Every candidate ran the complete TTT-009 frozen benchmark (77 actions)
and TTT-014 closed-loop suite (72 actions). Execution success does not imply
runtime quality admission; see the final programme decision for the actual gates.

Frozen semantic worker source: `11e70686b09a27cf7c784beaf8d7a46717b345a0`. Native checkpoint SHA-256:
`1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a`.
Seed 24301 and the admitted model profile are shared across all four fine-tunes.

The corpus contains 36 admitted episodes and 252 examples: T1 96, T2 96, T3 60,
with 210 train and 42 development examples split by scenario family. It contains
zero frozen benchmark examples. Full source episodes, provenance, enrichments,
manifest and exact shards are preserved under `corpus/`.

| Variant | Training examples | Optimizer steps | Training loss | Reload parity |
|---|---:|---:|---:|---|
| prompt-only | 0 | 0 | n/a | n/a |
| operational | 210 | 27 | 0.399509 | passed |
| persona | 210 | 27 | 0.833369 | passed |
| joint | 180 | 23 | 0.894153 | passed |
| joint+corrective | 210 | 27 | 0.742804 | passed |

All completed candidates ran on NVIDIA TITAN RTX UUID
`GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8`. The initial V100 prompt-only attempt
lost its CUDA device after 42 actions; its complete available outputs, error,
budget snapshot and hardware diagnosis are preserved under `failed-attempts/`.
The owner then required TITAN-only execution. The numeric-index supervisor was
stopped while the healthy TITAN operational worker continued. The recorded
`continue-titan.py` launcher verified the exact CUDA UUID before every remaining
worker and resumed the original budget ledger without changing training or
evaluation code. No reboot or GPU reset was attempted.

The live checkout received an unused optional LangGraph backend typing/lazy-import
patch while processes were active. `source-audit-live/` preserves the complete
status, tracked patch and source hashes at discovery. Training, evaluation,
authority, schema, renderer and recording semantics remained unchanged. This is
an explicit provenance caveat for processes already started; the full working
tree is not claimed to have stayed clean. Remaining workers imported the archived
immutable `worker-source-11e7068.tar` through a checked PYTHONPATH, recorded in
`continue-titan-frozen.py` and the campaign's source provenance override.

The conservative total charged budget is 0.962306
GPU-hours, including the failed attempt and 0.01 GPU-hours for preflight. External
compute and paid API costs are both £0. The request cap was four GPU-hours,
within the admitted 24 GPU-hour ceiling. The operational and persona workers whose
supervisors were stopped are charged from their recorded OS process creation
through observed completion plus a 30-second guard each; all other workers use
supervised wall time.

`execution-summary.json` records generation token counts, measured rates and
limitations. T2 is a local deterministic template-teacher contribution with
explicit research provenance; it is not live admitted-model generation. T3 uses
scripted student failures with real authority feedback. The persistent relay goal
and changed closed-loop mission priority are both model-visible and apply equally
to every candidate. The small one-epoch pilot does not establish broad quality.
Joint uses 180 mapped training rows and 23 optimizer steps; the other mixes use
210 rows and 27 steps. The common one-epoch profile therefore compares the
complete dataset mixes and does not isolate extra T3 content from extra exposure.
The scripted corpus policy shares reference-baseline style vocabulary
(`Glass-throne`/`sunrise-vector`). Zero reserved world examples are included;
persona keyword proxies therefore are not evidence of held-out-persona
generalization and must be read alongside repetition and manual ratings.
Training spans eight turns and carries generation in `world_state_id` (`:gN`);
evaluation adds `observation_generation` and tests prelude/reopen offsets over
24 turns. Stale-generation failures apply to this recipe under that shift and
do not establish an intrinsic limit of the admitted model family.

Each candidate directory preserves raw generations and actions, reports,
identity, parity and run metadata. `artifact-index.json` binds every local
checkpoint/adapter file, states what is packaged and records omitted weights.
Large weights remain in the ignored local artifact directory. Logs and dependency
text use portable LF endings; original byte hashes remain in the artifact index.
`licenses/` carries the exact admitted upstream LFM license text, with provenance
and original/portable hashes, alongside the exported tokenizer/adapter metadata.
`SHA256SUMS` covers every portable file except itself, including the completion
marker. No failed result or partial V100 response was silently replaced.
