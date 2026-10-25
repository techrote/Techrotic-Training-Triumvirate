# TITAN commander continuation evidence

This continuation pursues a trained commander passing the original admission
gates. The initial TTT-016 negative study remains immutable. No passing final
admission is asserted by the records below.

## Attempt-03: completed training, rejected development

Executed semantic source: `0c50c693c0c85d2fedfa3d173a01b9cea9bd2e07`.
Training run: `ttt-012-train-export-03d651cb145e0231`. The registered profile-v2
trained the admitted native LFM2.5-1.2B checkpoint for three epochs, 1,464 optimizer
steps, using corrected corpus-v3. The [data card](data-card.md) records its exact
identities, composition and limitations. All GPU execution used physical TITAN
RTX UUID `GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8`.

| Fresh development metric | Result | Required promotion threshold |
|---|---:|---:|
| Mechanical score | 0.7071611722 | 0.95 |
| Rejection recovery | 0.0512820513 | 0.80 |
| Objective completion | 1.0 | 0.80 |
| Critical detections | 0 | 0 |
| Native adapter reload parity | 3/3 exact strings | Pass |

All 77 development model actions are preserved. The model secured objectives,
then repeatedly assigned the already secured target and failed to recover from
the resulting precondition rejection. An initially secured development case
also exposed this behavior. The shared input serializer did not compensate for
the corpus's missing single-objective/optional-mission configurations.

The development gate rejected this candidate before frozen evaluation. There
is no frozen benchmark, 24-turn final readout, final Q4 qualification or human
rating for this attempt. Objective completion and reload parity are not admission.

The [attempt-03 snapshot](attempt-03/) contains the actual reports, raw model
actions, identity, training result, parity strings, run manifest, corpus manifest,
raw worker log and allocation ledger at completion. `SHA256SUMS` binds every
snapshot file. This is diagnostic execution evidence, not a positive admission
package. Large adapter/model binaries and full source corpus remain local under
`artifacts/ttt-017/`; restoring this snapshot alone does not restore those binaries.
The actual adapter SHA-256 is
`5b9898866b7fbd1fd023a8b13fbbe2daf116860df06d04d32e705ac4c426f7bf`.

Attempt-03 charged 1.1863411111 GPU-equivalent wall-hours, including native
evaluation. Including failed attempts and the conservative device probe, the
continuation had charged 1.4592622222 of its 22-hour allocation at this snapshot.
The initial study's separate historical consumption is 0.962306 hours. No V100,
paid API or external compute was used.

Subsequent repairs use fresh training worlds and explicit new source/dataset/run
identities. The prospective admission thresholds remain in document19. The
deterministic orchestration plan is in
[issue #43](https://github.com/techrote/Techrotic-Training-Triumvirate/issues/43);
its general controller implementation is a later task.

## Owner-requested pause: 24 October 2026

Attempt-04 is paused after all 1,473 optimizer steps (three epochs) and three
exact native adapter reload-parity fixtures. Native development/frozen evaluation
had not started. No commander is admitted. The owned workers and continuation
helper are stopped, both leases are released, and the reconciled continuation
charge is 2.5533377778 of 22 GPU-equivalent hours. GPU execution used only the
admitted TITAN RTX UUID.

The [pause handoff](pause-handoff.md) records the candidate and source identities,
unchanged admission thresholds, local artifact inventory, process ownership,
accounting, outstanding work and concrete resume commands. The checksum-bound
[pause proof bundle](pause-2026-10-24/) preserves the actual training/parity
records and full worker log. Large weights remain local. Resume only on the
owner's instruction, by verifying and evaluating the completed adapter without
repeating optimization. PR #42 remains draft and issue #41 remains open.

## Resumed on 25 October: machine gates passed, human review pending

[Attempt-04 qualification evidence](attempt-04/) preserves the completed native
evaluation, original Q4 latency miss, explicit graph-disabled Q4 pass and export
lineage. Both native and Q4 frozen/24-turn behavioral gates pass. The final
measured configuration has 0.0543073-second maximum TTFT, 290.001518 tokens/s
median decode and 1.351 GB peak server working-set RSS for the 730.895 MB Q4.
The initial 6.972509-second latency miss is retained. Total continuation charge
is 2.7592925 hours, with no outstanding reservation or active owned GPU worker.

The goal is incomplete while genuine blinded ratings and strict final package
readback are pending. The review packet is ready and the owner has been asked
for scores. No scores or ADMITTED result have been generated. PR #42 was merged
while this chat was paused; new evidence uses a follow-up qualification branch.
The [current handoff](qualification-handoff.md) supersedes the historical pause
state for further work.
