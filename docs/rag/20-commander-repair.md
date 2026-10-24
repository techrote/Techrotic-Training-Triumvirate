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
