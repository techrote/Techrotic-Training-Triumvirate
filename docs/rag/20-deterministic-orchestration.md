# TTT-018 deterministic experiment orchestration

Status: non-GPU controller implementation complete on the TTT-018 feature branch.
The final explicitly budgeted TITAN integration remains a hardware acceptance step.

## Contents

1. Scope and boundaries — what this implementation completes without GPU execution.
2. Identity and persistence — immutable plans, WAL storage and event replay.
3. Scheduling and ownership — reservations, physical-device leases and worker identity.
4. Worker containment — detached deadline host, Windows Job Objects and cancellation.
5. Pipeline adapters — reuse of corpus, checkpoint, parity and admission verification.
6. CPU qualification — real conversion/Q4 diagnostics without named-host substitution.
7. Evidence classes and rehearsal — hard separation of actual, CPU and simulation evidence.
8. Remaining hardware work — the only TTT-018 acceptance work intentionally left open.

## 1. Scope and boundaries

TTT-018 adds a dependency-light deterministic controller under
src/techrotic_training_triumvirate/experiments. It does not replace the existing
training, evaluation, runtime or admission implementations. The controller owns
durable orchestration and calls those components through narrow verification
adapters.

The implementation is intentionally GPU-free in default CI. The public
experiments run command validates and persists a real plan, then stops in
PREFLIGHT. It does not silently reserve a GPU or launch training. The full
rehearsal command is available only for a simulation plan and can finish only
with TEST_ONLY disposition.

PR #42 / issue #41 is concurrently changing the live commander-training path,
including native CUDA UUID handling. TTT-018 therefore does not duplicate those
in-flight training-source edits. After #42 lands, this controller consumes that
interface through the existing training modules.

## 2. Identity and persistence

ExperimentPlan is immutable and its experiment ID is derived from canonical JSON
content. It binds the source archive, semantic commit, model identity, dataset
identity, training-profile identity, admitted physical GPU UUID, CPU/GPU time
budgets, artifact root and simulation status.

ExperimentStore uses SQLite WAL with synchronous FULL writes, foreign keys and
BEGIN IMMEDIATE transactions for mutations. It persists experiments, an
append-only event journal, attempts, budget reservations, physical-device leases,
artifact inventories and review records.

Each event records a deterministic event ID, monotonic sequence, parent-event
hash, explicit timestamp, typed payload and before/after states. Re-delivery of
the same event content is idempotent. Replay recomputes the complete hash chain
and pure transition sequence; materialized state must agree with replay.

Unknown interrupted reservations are charged at their full cap. A reservation
must exist before WORKER_LAUNCHED can be accepted. Source/config changes produce
different stage or attempt identities rather than rewriting an old attempt.

## 3. Scheduling and ownership

GPU time and CPU time are accounted separately. The complete declared cap is
reserved transactionally before launch and reconciled only after the worker exit
is established. Ambiguous lifetime retains the full reservation.

A physical-device lease is separate from budget accounting. The lease binds the
immutable plan UUID, experiment, attempt and launch nonce. SQLite permits only
one active lease for a physical UUID. WORKER_LAUNCHED requires all three durable
records: registered attempt, active GPU reservation and active device lease.

Attempts carry a stage identity, ordinal, launch nonce, source hash and config
hash. A consumed ordinal/nonce cannot be relabelled as a different attempt.

## 4. Worker containment

WorkerSpec contains a fixed argv array and environment; it does not accept shell
text. A detached worker host owns the process deadline independently of the
controller. On POSIX the worker is placed in its own process group. On Windows
the host creates a named Job Object with kill-on-job-close and assigns the child
before recording ownership.

OwnedProcess records PID plus an OS process-creation token, attempt identity,
source/config hashes and launch nonce. Cancellation first verifies that the PID
still has the same creation token, preventing a reused PID from being killed as
if it were the old worker.

The host writes an ownership record, watches its own hard deadline and explicit
stop record, applies a bounded grace period, and then terminates only its owned
process tree. Worker stdout/stderr is retained in the attempt log.

A successful process exit is not artifact completion. The artifact layer hashes
closed files, fsyncs them and atomically publishes COMPLETE.json. The controller
then independently verifies every file and the marker before a stage can use the
inventory.

## 5. Pipeline adapters

The orchestration layer reuses the existing project gates rather than cloning
their logic:

- training.data.load_corpus_examples for manifest, shard hash and split checks;
- campaign_integrity.verify_checkpoint_identity for exact resume identity;
- campaign_integrity.verify_training_reuse for completed native training,
  artifact inventory and reload parity;
- training.export.sha256_file for exact artifact bytes;
- admission.verify_package for final strict admission-package readback.

The controller adds its own stage completion marker around these artifacts. This
keeps orchestration crash/restart semantics separate from model-training logic.

## 6. CPU qualification

CpuQualificationSpec can run an actual declared converter, quantizer and
inference command when those tools and inputs are locally available. Commands
are argv arrays, shell execution is disabled, deadlines are bounded, CPU threads
are capped through the environment, CUDA visibility is cleared and stdout/stderr
are hashed.

The diagnostic records exact F16 and Q4 artifact sizes/hashes, host identity,
limits and stage timings. Its evidence_class is always cpu_diagnostic,
admission_substitute is always false and named_host_acceptance is always false.

This permits real GGUF/Q4 engineering work on a CPU host without claiming that
the required named deployment host has passed the original runtime gate.

## 7. Evidence classes and rehearsal

Evidence is one of actual, cpu_diagnostic or simulation. A simulation experiment
cannot cross the actual-admission boundary. CPU diagnostics may coexist with
actual evidence but cannot substitute for it. The existing final admission
verifier remains responsible for the disposition-specific human/runtime gates.

The deterministic rehearsal executes the complete state machine with no model or
LLM calls. It exercises preflight evidence, a simulated GPU reservation and
physical-device lease, training completion marker, development selection, CPU
export reservation, conspicuously fake Q4 fixture, simulated runtime
qualification, frozen-evaluation fixture, supplied test review and final
readback.

The only valid final rehearsal disposition is TEST_ONLY with
qualifies_candidate=false. Tests also cover event redelivery, restart replay,
budget exhaustion, unknown-lifetime charging, exclusive leases, GPU-worker
failure, corrupted/missing artifacts, stale checkpoint identity, process
deadline enforcement, PID-reuse refusal and unavailable CPU tooling.

## 8. Remaining hardware work

TTT-018 remains open for the final hardware acceptance item:

1. Reconcile the #41 / PR #42 native UUID hardening into main.
2. Supply an explicitly authorized real ExperimentPlan and source archive.
3. Run preflight against the admitted TITAN RTX UUID.
4. Execute the bounded real training/export/runtime/frozen pipeline under the
   controller with actual artifacts and genuine human review.
5. Verify named-host Q4 measurements and the strict final admission package.
6. Record actual resource use and the real disposition.

Nothing in the simulation or CPU diagnostic path is evidence that a trained
candidate passed those steps. A failed hardware run remains a preserved failed
attempt and does not invalidate the completed non-GPU controller work.
