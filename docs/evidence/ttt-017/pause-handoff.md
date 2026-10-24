# Commander continuation pause and resume handoff

Owner request: pause at a coherent milestone within the next 10–30 minutes.
The chosen milestone is all three training epochs plus verified saved-adapter
inventory and three exact native reload-parity fixtures, before full native/Q4
qualification. The fallback is a complete optimizer/scheduler/RNG checkpoint if
training slows beyond the window.

**Paused at the completed-training and exact-reload-parity milestone.**
The adapter is saved and canonically verified. No commander has been admitted.

## Objective and constraints retained on resume

Continue until an actual trained commander passes the unchanged admission gates.
Do not substitute a completed training job, lower loss, synthetic human scores,
interim diagnostics or a conditional outcome for ADMITTED.

Use only physical TITAN RTX UUID
`GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8` for GPU execution. No V100 work,
reset, index-based fallback, cloud compute or paid model API. CPU-only preparation
and diagnostics are allowed. Avoid broad `nvidia-smi` inventories: the unrelated
V100 has a lost-driver condition. GPU workers must select the UUID before CUDA
imports and verify the actual device before model loading.

The continuation allocation is 22 GPU-equivalent wall-hours including failed
launches, training, evaluation and runtime probes. Reserve the full stage cap
before launch, reconcile only established owned-process lifetimes, and retain
unknown reservations conservatively. Original study consumption is separately
preserved at 0.962306 hours. Never reset or omit historical charges.

## Workspace, issues and immutable sources

Resume in this existing Windows checkout on this host:
`C:\cybernpc2\Techrotic-Training-Triumvirate`.

- Branch: `feat/ttt-017-qualified-commander`.
- [Issue #41](https://github.com/techrote/Techrotic-Training-Triumvirate/issues/41):
  active trained-commander qualification work; leave open until genuinely complete.
- [PR #42](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/42):
  draft; do not merge unfinished qualification. Follow AGENTS.md review/check/merge
  requirements after completion.
- [Issue #43](https://github.com/techrote/Techrotic-Training-Triumvirate/issues/43):
  deterministic orchestration planning is complete. Keep open for the later
  general-controller implementation requested by the owner. Do not start that
  implementation merely to fill a wait in this training task.
- Active training/evaluation semantics:
  `f152cafc59bda5207b8cb1c5ef7d6d60133d1b41`.
- Archived source directory:
  `artifacts/ttt-017/source-f152cafc59bda5207b8cb1c5ef7d6d60133d1b41/`.
- Source ZIP SHA-256:
  `5d5e4ca5a88f09f5451451f4e825d26570e098ce6a18759f9552fa33570b2e01`.
- Separate CPU export/Q4 transport driver source:
  `8ba6a515f6a163642f945a3786b6b44044a2f2b4`, archived under its own source directory.
- Separate final reporter source:
  `c4ce567d59d947d8c07ab98282eafb970e69f12e`.
  `scripts/build_commander_evidence.py` executed SHA-256 is
  `800c5b1ce88b24e8a29a9a7f4d99e8a8618a02f5dbfc08581b2ead1f93729854`.

Do not relabel training as a later live HEAD. Documentation/handoff commits may
follow these sources without changing their executed code identities. GitHub has
code and small evidence; large weights, corpus files and tool archives remain
local under ignored `artifacts/`. A fresh checkout does not restore those files.
No model publication has been authorized.

## Current candidate and data

The base is admitted `LiquidAI/LFM2.5-1.2B-Instruct`, exact native revision
`205939ab34ce3eaa85f527376fe3f425fcefa782`. The native model file is available as
an ordinary local hard link at
`artifacts/ttt-017/admitted-native/model.safetensors`, 2,340,697,936 bytes, SHA-256
`1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a`.
It links the verified Hugging Face cache file; do not overwrite it.

Attempt-04 uses `artifacts/ttt-017/corpus-v4/` and curriculum version 3, seed 938000.
Its [data card](corpus-v4-data-card.md) contains all identities and limitations.

- Dataset SHA-256:
  `028dfa357fd91e10e4aaa982deff583b4de0fae49e320e29df3a167de9822105`.
- Manifest file SHA-256:
  `b09e1375b78476234c809ba3d36e1d10b3fb30577052377f61d6f3829674b918`.
- Source episode archive SHA-256:
  `5dbcea3ad9612bc4f506ff32dc4bc548e3e7cc9e165f367878745d060031c35a`.
- Train/dev shard SHA-256:
  `1dd87e065119c854a9ea0dd927877491e5f504b026bb7b34dd4ca25a94593777` /
  `69c838793e7995c8f536be93c57609064861ca8eeffad7860e7fc8c4f1ae3bc1`.
- 168 authority-validated 28-turn episodes; 3,924 training and 654 development rows.
- One/two objectives, two/three units, optional mission/private extensions,
  initially secured objectives, actual rejection feedback, reopening and stalls.
- Episode/seed splits are disjoint; abstract generator families/styles overlap.
  Scripted teacher contribution only; no model-generated teacher or actual learned
  rollout collection. The corpus licence remains internal research with
  redistribution ungranted pending owner review. Native LFM licence/notices apply.

Registered profile-v2: joint+corrective LoRA, rank 16/alpha 32/dropout 0, all-linear,
three epochs, LR 0.0002, microbatch 4/accumulation 2, sequence 2048, seed 24302,
save every 50 steps, native chat template and assistant-only loss, parity generation 192.
The complete schedule is 1,473 optimizer steps. Native policy ID remains
`commander-repair-v2` and codec `ttt-commander-wire-v2`; the version 3 label refers
to the curriculum, not a scripted policy replacing model decisions.

The model owns every tactical field and observation generation. The host adds
fixed record/envelope fields only; invalid/stale output is not repaired.

## Execution records and pause mechanics

Primary local records:

- `artifacts/ttt-017/attempt-04/`: canonical training identity, final adapter,
  training result, parity and run manifest from the completed milestone.
- `artifacts/ttt-017/allocation-ledger.json`: cumulative authoritative accounting.
- `artifacts/ttt-017/pause-request.json`: explicit pause plan and process ownership.
- `artifacts/ttt-017/pause-stop-intent.json`: verified boundary before termination.
- `artifacts/ttt-017/pause-result.json`: final pause state, hashes and reconciled charge.
- `artifacts/ttt-017/pause-watcher.log`: owned pause-controller output.
- `artifacts/ttt-017/qualification-state.json`: current pipeline state.

The original worker was PID 32216, creation time 1792851769.4452362 (Unix seconds).
Its exact command is in the pause plan. The continuation helper PID 21260 was
explicitly stopped before the milestone so it cannot launch Q4 work during pause.
PIDs are historical evidence, not permission to kill a process after resume:
revalidate PID, creation time and exact command against live OS state first.

After the owned worker stops, its CPU supervisor must reconcile the ledger and
release `allocation.lock`. The pause watcher archives the original worker log and
any partial native evaluation artifacts under
`attempt-04/paused-phase-01/`, preserving their hashes. Training identity/result,
adapter, parity and run manifest remain in place. A missing `worker-complete.json`
means the complete native evaluation workflow has not finished; do not fabricate it.

## Resume procedure after the complete-training milestone

First read the final pause state below, verify no unexpected owned job or lease
is active, and inspect the ledger. Never restart solely because an old observation
session expired. Use `.venv-training/Scripts/python.exe`; do not modify the active
training environment or archived source. Dependencies include torch 2.7.1+cu118,
transformers 4.57.6 and peft 0.18.1.

CPU-only verification should load corpus-v4 and call
`verify_training_reuse` with the archived source, admitted primary binding,
profile-v2 joint+corrective seed 24302, and source revision f152caf. Compare actual
parity strings and adapter/run-manifest hashes with the final pause state.
The original negative evidence in TTT-016 must still verify.

If training is complete but native evaluation is incomplete, the existing archived
worker can reuse the canonical training result without another optimization run.
The old `worker.log` must already be archived; never delete an existing log to
bypass the supervisor's guard. Run from the repository root in PowerShell:

```powershell
$taskRoot = 'C:/cybernpc2/Techrotic-Training-Triumvirate'
$taskSource = 'f152cafc59bda5207b8cb1c5ef7d6d60133d1b41'
$env:CUDA_VISIBLE_DEVICES = ''
$env:PYTHONPATH = "$taskRoot/artifacts/ttt-017/source-$taskSource/src"
& "$taskRoot/.venv-training/Scripts/python.exe" -u `
  "$taskRoot/artifacts/ttt-017/source-$taskSource/scripts/train_commander.py" `
  --corpus "$taskRoot/artifacts/ttt-017/corpus-v4" `
  --output "$taskRoot/artifacts/ttt-017/attempt-04" `
  --git-commit $taskSource `
  --gpu-uuid GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8 `
  --hours 2 --epochs 3 --frozen
```

The supervisor is CPU-only and selects the TITAN in its child before imports.
It reserves a new cap in the existing ledger; the worker detects and verifies the
completed training result, skips SFT, loads that exact adapter and performs fresh
native evaluation. Keep historical pause charges. A reused output path here is
intentional canonical training reuse after preserving the previous phase's logs.

**Wait for that supervisor to exit and release the lease before starting the
continuation helper.** The helper's original in-progress lookup selects the first
matching output entry; starting it early against a reused output could confuse the
historical paused entry with the new reservation. Once worker completion exists
and the lease is gone, its wait loop is skipped. If native development rejects
the candidate, preserve that rejection and diagnose it before another experiment.

After successful native workflow completion:

```powershell
& "$taskRoot/.venv-training/Scripts/python.exe" -u `
  "$taskRoot/artifacts/ttt-017/continue_qualification_04.py"
```

This purpose-specific helper checks native gates, then runs CPU merge/export,
reserves at most 0.5 hours for TITAN Q4 qualification, replays the final evidence,
creates the scoped scripted-control comparison and blinded packet, and enters
WAITING_FOR_HUMAN. It is not the durable controller planned in #43. Its current
SHA-256 is `728bbb31fc72b1c374b87e5215fd8be27c0bee3365b228551667d7e42554b50a`.
It requires a fresh export/Q4 output; preserve failed derivatives and use fresh
names with separately recorded launcher identity if a rerun is necessary.

If the pause instead used an incomplete checkpoint, do not run the ordinary CLI
as though it automatically resumes the optimizer. Use the final checkpoint and
its recorded hashes, the same config/data/source identity and the existing
`run_hf_peft_training(..., resume_from_checkpoint=...)` backend contract under
a newly reserved UUID-pinned stage. Preserve optimizer, scheduler and RNG state;
do not silently restart SFT or relabel a changed configuration.

## Qualification still required

The exact thresholds remain in [document19](../../rag/19-final-admission.md) and
the original model-cast runtime targets:

- Fresh native development seeds962000+ must pass before the frozen readout.
- Frozen mechanical score >=0.95 and rejection recovery >=0.80, substantive commands.
- Three frozen24-turn episodes: objectives >=0.80, execution-failure recovery >=0.80,
  schema >=0.95 and repetition <=0.50.
- Zero critical secret/fabrication/intercept detections; automated detectors have limits.
- Real native reload parity and immutable source/model/data/run/export provenance.
- Actual final Q4_K_M: context >=2048, artifact <=1,000,000,000 bytes,
  peak server RSS <=3,000,000,000 bytes, streamed TTFT <=2 seconds,
  sustained decode >=12 tokens/second on the named host.
- Genuine blinded human1–5 humour/surprise/distinctiveness ratings. The existing
  policy requires supplied review but sets no minimum score. Never invent scores,
  infer them from silence or reveal the group identity key before review.
- Strict final package readback with all required local binaries available.

After machine gates pass, ask the owner for actual A/B group ratings from the
generated review packet. Keep the group key separate until scores are supplied.
Then use `scripts/build_commander_evidence.py` with the exact training/evaluation/
export/corpus/comparison paths, actual canonical human record, corpus-v4 data card,
local admitted-native hard link, fresh final output, semantic sourcef152caf and
reporter sourcec4ce567. It refuses incomplete/changed evidence and publishes a
local result directory only after strict readback. A clean clone needs the exact
hash-bound local binaries restored; no weight publication is implied.

Update cards/report/README/RAG and PR #42 around the actual final result. Run the
required tests/checks, self-review, observe CI, mark ready and merge only after
the full objective is achieved. Verify #41 closes. Keep #43 open for later work.

## Useful historical evidence

Attempt-01 failed before model load on the native UUID-object type. Attempt-02
was deliberately stopped after an interim probe exposed a squad-assignment bug.
Attempt-03 completed 1,464 steps and three exact parity fixtures but was rejected
on 77 fresh development actions: mechanical 0.707161, rejection recovery 0.051282,
objectives 1.0, zero critical detections. Its frozen readout was withheld. The
committed [attempt-03 snapshot](attempt-03/) is checksum-bound and all 77 actions
authoritatively replay in default CI. Do not rewrite these failures.

Attempt-04 checkpoint 550 CPU-only diagnostics on seeds 964100–964102 produced 24/24
accepted actions over three 8-turn worlds, handled already-secured feedback and
reopening, and recovered an actual delayed failure for the same unit and target.
These are incomplete-checkpoint development diagnostics, not admission evidence.
Raw inputs/actions/events are under `artifacts/ttt-017/interim-04-550-development/`.
The diagnostic server has exited. Its Q4 SHA-256 is
`1121c71d4311ef313573a94b7bd7ff5ac4f74cba38d4af564f496afbd80de8b5`;
checkpoint adapter SHA-256 is
`0b72845351105848761e04cbc30f2c8d551fbf14550411fed24d639cbde237b7`.

Latest code validation: 349 tests passed, one optional Concordia skip; Ruff checks,
formatting and strict mypy passed. Focused reporter tests also passed after the
final allocation guard refinement. CI was green on c4ce567. Tests distinguish
synthetic verifier fixtures from actual model/human evidence. The initial
TTT-016 negative package remains intact and verifies without model downloads.

## Final pause verification

Paused at **2026-10-24 15:28:28 UTC**, **15.361 minutes** after the request, within
the requested 10–30 minute window. The full-training milestone was reached; the
checkpoint fallback was not needed.

| Item | Verified state |
|---|---|
| Training | 1,473 optimizer steps; epoch 3.0; 3,924 training examples |
| Native reload parity | All three actual pre/post output strings equal |
| Training run | `ttt-012-train-export-791d6d18b367582e` |
| Adapter SHA-256 | `daa08ab3f0c1e7fd876626f44f96eb0748a8eebc0386ab7a6d1ffa949ddb6eb0` |
| Run-manifest SHA-256 | `c7b7b75b1323395d73fcc9bf9fa1c36337b1b0a6f6881be65ae0c23981d0d8a8` |
| Parity file SHA-256 | `f7a12dea6c6ac5d7eec21d88fb464857e8d981c0b4c6bc79d7ab81676573b7ab` |
| Actual physical device | NVIDIA TITAN RTX; admitted UUID verified |
| Canonical training reuse | Independently verified against all nine saved artifacts |
| Native development/frozen evaluation | Not started; no model-action prefix or reports |
| Final export/Q4/runtime/human review | Not started |
| Owned worker/helper/pause-controller | Terminal; live OS readback found none |
| Device and continuation leases | Both absent |

Attempt-04 charged **1.0940755556 GPU-equivalent hours**. Cumulative continuation
charge is **2.5533377778 of 22 hours**, leaving **19.4466622222 hours** in that
allocation. There are no outstanding reservations. The supervisor recorded
status 15 because the pause controller intentionally terminated the worker after
training/parity verification; this is an owner-requested pause, not an SFT failure.
The training result and artifact inventory remain valid and unchanged.

The complete worker log is preserved at `attempt-04/paused-phase-01/worker.log`,
SHA-256 `039c560891c4cfda329554856bcacf8f3182e17563a9e82d70098b8febdff59a`.
No partial native evaluation files were produced. The active output directory has
no `worker.log`, allowing the documented supervisor to reuse completed training
and create a fresh evaluation-phase log on explicit unpause. `worker-complete.json`
is intentionally absent because the full native evaluation workflow has not run.

The committed [pause proof bundle](pause-2026-10-24/) includes the actual pause
request/stop/result, process/lease readbacks, reconciled ledger, corpus/training
identities, parity strings, training result, manifest, raw worker log and controller
source. Its `SHA256SUMS` covers every bundle file. Large weights remain local.
The original TTT-016 negative package still verifies 133 bound files with content
SHA-256 `919a4f66476c67c195fdad3d2037480ecf5d663463993e01ce5c2db17fdcb265`.

**Next action on explicit unpause:** verify this saved training result, then run
native development/frozen evaluation using the existing archived worker's reuse
path. Do not repeat optimization or resume an older intermediate checkpoint.
Only start the continuation helper after that native supervisor finishes and
releases its lease. All original admission gates, actual Q4 measurement and genuine
human review remain outstanding. PR #42 stays draft and #41 stays open.
