# TITAN-only admission continuation

Owner request and execution allocation: issue #41. The initial NOT ADMITTED
study remains immutable. New training/evaluation source and dataset identities
are separate. The new allocation is 22 single-device GPU-hours, including failed
attempts and GPU probes, with £0 external compute and £0 paid APIs. Historical
initial consumption is 0.962306 GPU-hours. Each attempt reserves its cap before
launch; interrupted unknown reservations remain fully charged. Budget exhaustion
is a hard stop, not an admission or completion.

All heavy workers select physical TITAN RTX UUID
`GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8` before importing CUDA, and verify actual
device UUID through the existing admission helper before loading a model. V100
work, enumeration-dependent selection and GPU resets are forbidden. Run archived
committed sources using an explicit PYTHONPATH; never relabel changed live code.

## Distribution and output repairs

The initial corpus used different input projections, short eight-turn episodes,
almost no long-session/reopened objective exposure, and only one epoch. Its model
memorized stale generations, malformed envelopes and repetitive speech. The new
pipeline uses exactly `commander_input(EvaluationContext)` for training and model
inference. It includes current generation, admitted facts, objective/entity IDs,
persona and actual previous feedback/events. It excludes case kinds, evaluator
labels and hidden world state. Private commander facts remain confidential inputs.

`ttt-commander-wire-v2` removes transport record/schema IDs from model prediction.
The model emits `{"command": <typed command body>, "speech": <text>}`. The host
adds deterministic IDs, versioned wrappers and the fixed public communication
channel. It supplies no tactical values. In particular, the model still emits
its own observation generation, op, unit, target and approach. Stale, invalid or
malformed decisions are rejected unchanged; no scripted fallback is available.
Every emitted raw reply, parsed action and generation timing is preserved.

Fresh seeded 28-turn worlds exercise independently timed objective pressure,
reopening, random initial generation offsets, capability rejection and actual
delayed execution stalls. Environment probes are archived and authority-validated
but excluded from supervised targets. The oracle sees only admitted observations
and feedback. The canonical corpus assembler validates source episodes before
aligned views are serialized; splits are episode/seed disjoint. Abstract generator
families and deterministic style vocabulary overlap; broad generalization or
human character quality is not inferred from these demonstrations.

Source episodes, manifest, shards, config, base identity, native artifact hashes,
training identity, parity and run manifest bind each run. Assistant-only loss and
native tokenizer chat templates are retained. The initial repair profile uses
LoRA rank16/alpha32, three epochs, LR0.0002, microbatch4/accumulation2, sequence2048,
seed24302. Development uses independent seeds960000+, excluded from training;
frozen benchmarks and admission thresholds remain unchanged. No frozen response
or failure is copied to training. Any repeated frozen selection is disclosed.

Unconditional admission still requires actual trained Q4 measurements and genuine
human ratings. A prepared packet, synthetic ratings or passing native loss/parity
does not fill those gates. Follow the original schemas and thresholds in document19.

## Early execution corrections

The first guard check refused before model load because torch2.7 returns a native
UUID object; converting its canonical string retains exact physical UUID checks.
The failed launch is charged and preserved. An interim CPU-only export from the
second attempt exposed a demonstration bug: observed objective IDs are sorted,
not ordered by mission assignment. That attempt was deliberately stopped and
retained. Corrected demonstrations associate the source world's primary relay
with unit1, use unit2 for secondary objectives, and must prove recovery of every
actual delayed failure with a later authoritative objective-completed event for
the same unit/target. Environment probe commands never become supervised labels.

The exact predeclared profile is registered as `profiles_v2.json`. Admission
readback resolves the recorded version to that registry and compares the full
configuration, run hash and source-bound identity. Arbitrary profile versions,
changed epochs or unsupported mixes remain refused. Outcome thresholds are
unchanged. Corrected corpus seeds start at934000; development remains960000+.

## Trained Q4 qualification

The CPU-only merge/export scripts require a completed native worker, verified
canonical training identity/artifact inventory and the admitted base. They check
the actual converter source and extracted executables/DLLs against the digest-bound
official llama.cpp b8185 archives, merge the actual adapter, convert to F16 GGUF,
quantize to Q4_K_M and inspect actual GGUF metadata. Their manifests bind every
parent and derivative hash. Interim checkpoints cannot enter this qualification
path; separately labelled CPU diagnostics are not admission evidence.

The external HTTP transport imports the archived training/evaluation semantics
and verifies those files against their semantic commit. Its own later source
commit and file hash are recorded separately. It verifies the Q4/adapter/base
lineage, runtime binary and served model alias before using real model responses.
The model makes every command decision; no grammar, fallback or stale-generation
repair hides output failures. Final evaluation runs again on the Q4 derivative.

Runtime evidence measures actual artifact bytes, a 2,048-token context, server
working-set RSS sampled every 20ms, real streamed first-content-token latency
with prompt caching disabled, and separately measured sustained decode. The
conservative maximum of three TTFT probes and median decode rate are reported.
Startup and GPU buffer logs remain available separately; training memory does
not fill this gate. The server is UUID-pinned, runs only after the training lease
is released, and has its own hard deadline. GPU probes remain charged to the
same allocation. Actual human review is still required for ADMITTED.

## Deterministic orchestration follow-up

[Issue #43](https://github.com/techrote/Techrotic-Training-Triumvirate/issues/43)
contains the completed plan for a programmatic experiment controller; its
implementation is a later task. The plan uses an explicit state machine,
transactional reservations and UUID leases, immutable source/artifact identities,
owned process containment and deadlines, behavioral corpus preflight, finite
development search, verified export/runtime stages, and durable human-review
suspension. It requires zero LLM calls for a predefined admitted experiment and
preserves failures without manufacturing a positive admission.

The continuation's UUID-object failure, sorted-objective demonstration bug,
stopped run, interim diagnostics and missing original Q4/human evidence inform
the plan. A local helper sequencing this one experiment is not the durable
controller proposed there. Keep #43 open for that future implementation.

The corrected corpus has its own [data card](../evidence/ttt-017/data-card.md),
which records its byte identities and limitations independently of admission.

## Development-driven observation coverage

Attempt-03 completed all 1,464 optimization steps and passed native reload parity.
Its fresh development trajectories then exposed repeated assignments to an
already secured objective. Authoritative replay of those recorded development
actions confirmed `PRECONDITION_FAILED: target-already-secured`; this diagnosis
uses development evidence, not a frozen response copied into training.

Curriculum version3 adds single-objective worlds without the optional mission
extension, two- and three-unit worlds, mid-state starts, optional commander-private
extensions and initially secured objectives with actual rejection feedback.
Version2 always supplied two objectives and an explicit mission extension; sharing
the serializer alone did not cover the input configurations used by an independent
caller. Every fully secured demonstration must request status, including after an
actual target-already-secured rejection. Existing delayed-failure recovery and
authority validation remain required. Fresh version3 seeds begin at938000; the
registered training recipe and final admission thresholds are unchanged.

The completed attempt-03 development readout was mechanical0.707161,
rejection-recovery0.051282, objective-completion1.0 and zero critical detections.
All77 development actions are preserved. The worker withheld frozen evaluation
because the development gates failed. The next attempt uses independent
development seeds962000+ before any final readout.

## Final evidence assembly

`scripts/build_commander_evidence.py` assembles one completed continuation under
the existing TTT-016 admission schema. It performs no inference and creates no
human scores. Inputs name the completed training, Q4 evaluation/export, corpus,
blinded comparison, supplied canonical human-ratings record, matching data card,
actual admitted native binary, fresh output directory and distinct semantic/
reporter commits. All referenced files must resolve inside the explicit checkout
root; the native cache file can be restored as an ordinary local hard link under
the artifact root without duplicating its bytes.

The builder verifies the canonical training identity and inventory, original
operational/character gates, authoritative long-session replay, actual native and
Q4 binary hashes, F16/merged parent inventory, measured runtime binding, TITAN
readback and cumulative allocation. It then stages hard links and generated cards
under a private artifact directory. The unchanged admission verifier must accept
all evidence, runtime thresholds and actual ratings before the output directory
is published. Failed staging is removed; no proposed ADMITTED result is published.
The executed reporter files are bound to their own committed source.

The package references local binary artifacts by relative path and SHA-256.
Full readback on a clean clone requires restoring those exact binaries; metadata
alone is insufficient. The original negative package remains portable and intact.
The [corpus-v4 card](../evidence/ttt-017/corpus-v4-data-card.md) describes attempt-04's
specific training inputs; it does not assert qualification.
