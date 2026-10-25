# TTT-018 deterministic experiment orchestration

## Contents

1. Controller boundary — what the controller may decide and what remains authoritative.
2. Durable state — immutable identities, SQLite WAL, events, budgets and leases.
3. Worker containment — detached hosts, Windows Job Objects, deadlines and cancellation.
4. Existing-pipeline adapters — corpus, training, export and admission verification.
5. CPU diagnostics — real local conversion/inference checks that remain non-admission evidence.
6. Simulation and fault testing — deterministic rehearsal and failure preservation.
7. Operator CLI — current GPU-free commands and restart behavior.
8. Hardware-only completion — work that still requires the admitted physical GPU and real review.

## 1. Controller boundary

TTT-018 adds a dependency-light deterministic control plane under
`techrotic_training_triumvirate.experiments`. It does not replace World Authority,
training semantics, corpus validation, export verification or final admission
readback. Those existing modules remain authoritative and are called through
small adapters.

The controller consumes source-versioned plans and explicit verified events.
It never parses prose logs into decisions, edits Python during a run, invents a
successful action, changes frozen evaluation thresholds, generates human ratings,
or invokes an LLM. The pure transition function maps one persisted state plus one
verified event to the next state and a declared action list.

## 2. Durable state

`ExperimentPlan` identity is the canonical content hash of the complete plan:
allocation, creation timestamp, source archive, semantic Git commit, model,
tokenizer, dataset and configuration hashes, physical GPU UUID, budget, artifact
root, candidate set and evidence class. Stage and attempt identities derive from
that plan plus stage inputs, attempt ordinal and launch nonce.

`ExperimentStore` uses SQLite with WAL, full synchronous writes and immediate
transactions. It persists the plan, append-only hash-chained events, budget
reservations, exclusive physical-device leases, worker ownership records and
artifact inventory. Re-delivery of an identical event ID is idempotent; the same
ID with changed contents is rejected. Replay recomputes the entire parent-hash
chain and state machine and refuses a materialized state that differs.

The full GPU cap is reserved before an attempt. Active reservations count against
the cumulative allocation after restart. Established process lifetime may be
reconciled down to actual use; unknown lifetime retains the full reservation.
Reservations cannot be silently reset by reopening the database.

## 3. Worker containment

The worker host accepts a fixed argv array and environment; it never uses a shell.
The cwd must stay inside the admitted artifact root and the executable must be an
existing absolute file. Source hash, config hash and launch nonce are part of the
worker identity.

On Windows the host creates a Job Object, enables
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, assigns the worker process and keeps the
Job handle for the entire run. If the host dies, Windows closes the handle and
kills the contained process tree. On POSIX the test/reference path uses a separate
process group.

The host owns the hard deadline independently of the controller. Cancellation is
a request file watched by the host, not an indiscriminate PID kill. Controller
ownership includes PID plus an OS process-creation token, launch nonce,
source/config hashes and spec hash. A reused PID therefore cannot authorize
cancellation of an unrelated process. Cancellation now has a bounded grace
period before process-group or Job Object termination, and the state machine can
finish CANCELLING as terminal CANCELLED after owned-process exit is established.

Windows HANDLE-returning APIs declare pointer-width-safe ctypes signatures before
use. This prevents 64-bit Job Object or process handles from being truncated by
ctypes' default integer return type. The detached Windows host also uses an
explicit detached-process creation flag.

## 4. Existing-pipeline adapters

The controller reuses current project validators instead of duplicating them:

- `training.data.load_corpus_examples` for manifest/shard/split validation;
- `training.campaign_integrity.verify_checkpoint_identity` before checkpoint
  resume, so changed source/model/config/data cannot silently reuse stale state;
- `training.campaign_integrity.verify_training_reuse` for completed training,
  exact source/model/config/dataset identity, artifact inventory and native parity;
- `runtime.load_tiny_export` for dependency-free export/parity readback in CI;
- `admission.verify_package` for the existing fail-closed final disposition.

The real training and later GGUF/Q4 adapters can retain their own source identity.
A controller stage records the exact adapter/tool identity rather than relabelling
all work as a later repository HEAD.

Generic stage completion now has a separate durable contract: closed artifacts
are fsynced and hashed, then COMPLETE.json is fsynced and atomically renamed into
place. The controller independently re-hashes every declared artifact before
accepting that marker. A zero exit code or host-complete record alone therefore
does not establish stage completion.

## 5. CPU diagnostics

`ttt experiments cpu-diagnostic` can run an explicitly supplied local executable
with a fixed argv and no shell. This allows real GGUF conversion, quantization or
Q4 inference tools to be exercised when they are already available on the host.
The diagnostic records exact tool SHA-256, argv, stdout/stderr hashes, optional
artifact bytes/hash, host information, return code and elapsed time.

Every such record is permanently marked:

`evidence_class = "cpu-diagnostic"`

`admission_eligible = false`

`named_host_acceptance = false`

CPU diagnostics now clear CUDA visibility, cap OMP/MKL threads and request lower
scheduling priority by default. A first-class CPU Q4 qualification helper binds
three real subprocess stages in order: F16 GGUF conversion, Q4 quantization and
Q4 inference. It verifies that the F16 artifact does not change during
quantization and the Q4 artifact does not change during inference, then records
both hashes plus the three diagnostic records.

The admission-evidence guard rejects CPU diagnostics and simulation records.
These measurements can find conversion/runtime defects early but cannot replace
the named-host GPU runtime gate.

## 6. Simulation and fault testing

`run_rehearsal` executes the complete state sequence from PLANNED through
COMPLETE with deterministic doubles, a supplied review fixture, transactional
budget/lease operations and zero LLM calls. Its result and artifact inventory are
marked `simulation` and non-admissible.

Default CI exercises event replay/idempotence, changed-event rejection, restart
budget accounting, conservative unknown-runtime charging, exclusive device
leases, stale/non-admission artifact guards, stale checkpoint resume rejection,
atomic completion-marker corruption/missing-file rejection, worker
deadline/cancellation paths, terminal CANCELLED replay, PID creation-token
ownership and CPU diagnostic/Q4-chain recording. Corrupt or missing real pipeline
artifacts continue to fail through their existing validators.

## 7. Operator CLI

The GPU-free surface is:

```text
ttt experiments validate PLAN.json --db STATE.sqlite
ttt experiments status EXPERIMENT_ID --db STATE.sqlite
ttt experiments resume EXPERIMENT_ID --db STATE.sqlite
ttt experiments cancel EXPERIMENT_ID --db STATE.sqlite --reason TEXT
ttt experiments review import EXPERIMENT_ID ratings.json --db STATE.sqlite
ttt experiments verify EXPERIMENT_ID --db STATE.sqlite
ttt experiments rehearse --db STATE.sqlite --output DIR --review test-review.json
ttt experiments cpu-diagnostic --cwd DIR --output DIR --threads 2 TOOL [ARGS...]
```

`resume` currently means durable replay/reconciliation only; it does not blindly
relaunch the previous command. Real stage launchers should first bind the
corresponding existing pipeline adapter and obtain the required budget/device
lease.

## 8. Hardware-only completion

This implementation intentionally leaves physical qualification outside default
CI. Final TTT-018 acceptance still requires an explicitly budgeted TITAN
integration plan: actual UUID readback before model loading, real training or
canonical completed-training reuse, development/frozen evaluation, final Q4
runtime measurements on the named host, genuine non-test human review, strict
admission-package readback and one end-to-end run without continuous LLM control.

Simulation success, CPU-only runtime success, timeout, silence or a fabricated
review can never promote an admission experiment.
