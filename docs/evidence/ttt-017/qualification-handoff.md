# Commander qualification handoff: 25 October 2026

Current state: **WAITING_FOR_HUMAN**, not ADMITTED. The owner explicitly resumed
the task. Optimization was not repeated. Native and final trained Q4 machine
gates pass; actual local binary/source/lineage/budget checks independently pass.

## Preserved state

- Workspace: `C:/cybernpc2/Techrotic-Training-Triumvirate`.
- Branch: `feat/ttt-017-commander-qualification`; issue #41 remains open.
- PR #42 merged while paused, at `fad132ed2c99a416590f796e6035795530d624fe`.
  Its main changes and the independently merged controller work are integrated.
- Training/evaluation semantics: `f152cafc59bda5207b8cb1c5ef7d6d60133d1b41`.
- Native run: `ttt-012-train-export-791d6d18b367582e`; 1,473 steps, three epochs.
- Native/corpus roots: `artifacts/ttt-017/attempt-04`, `artifacts/ttt-017/corpus-v4`.
- CPU export: `artifacts/ttt-017/export-04`, original driver `8ba6a515f6a163642f945a3786b6b44044a2f2b4`.
- Failed runtime: `artifacts/ttt-017/q4-04`; keep its 6.972509-second TTFT.
- Final evaluation: `artifacts/ttt-017/q4-04-graphs-disabled`; transport source
  `ba904aad3c6640b524960f5c2a61dd8b4bc330d9`; explicit graph-disable setting.
- Final Q4 SHA-256: `2036e8c9a17038c0e503ae1af16a567673e59f37337f1cf09b40c2b2fdb819e0`.
- Only TITAN RTX UUID `GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8` was used.
- Ledger: `artifacts/ttt-017/allocation-ledger.json`, fully reconciled at
  **2.7592925 of 22 GPU-equivalent hours**. No live owned GPU job or lease.
- Frozen and long metrics: mechanical 0.9974358974; rejection, objective and
  delayed execution recovery 1.0; schema 1.0; repetition 0.0; critical 0.
- Q4 runtime: 2,048 context, 730,894,720 bytes, 1,351,196,672-byte peak server
  RSS, 0.0543073-second maximum TTFT, 290.001518 tokens/s median decode.
- [Snapshots](attempt-04/) preserve all native and both Q4 actions, full replay
  traces, runtime logs/samples and export lineage. Weights remain local.
- Current preflight: `artifacts/ttt-017/qualification-preflight-readback.json`.
- Current machine state: `artifacts/ttt-017/qualification-state.json`.

## Human boundary

The actual A/B packet was opened and an asynchronous question requested integer
1-5 humour, surprise and distinctiveness scores for each group. The packet is
`artifacts/ttt-017/comparison-04-graphs-disabled/review-packet.md`. Only its
instruction-line encoding was corrected; the generated original and hash-bound
presentation audit are retained alongside it. Excerpts/order/groups did not change.
Do not reveal or inspect `review-group-key.json` for presentation until ratings
are supplied. Never fabricate ratings, interpret silence as a score, or infer
human quality from automatic proxies. Existing policy has no minimum score but
requires genuine review. No positive package has been created.

After actual scores arrive, preserve the original user response and reviewer
provenance, read the separate group key, and create the existing canonical human
record with the actual candidate's supplied humour/surprise/distinctiveness
integers, candidate ID `commander-repair-v2`, schema `ttt.human_ratings`, version 1
and a unique nonempty reviewer ID. Keep any control scores in a separate record.
No runtime or training rerun is needed merely to await human review.

## Final assembly after genuine review

Use the unchanged builder with archived semantic modules. All actual local
binaries have already been checked; recheck if files moved or changed.

```powershell
$taskRoot = 'C:/cybernpc2/Techrotic-Training-Triumvirate'
$env:CUDA_VISIBLE_DEVICES = ''
$env:PYTHONPATH = "$taskRoot/artifacts/ttt-017/source-f152cafc59bda5207b8cb1c5ef7d6d60133d1b41/src"
& "$taskRoot/.venv-training/Scripts/python.exe" scripts/build_commander_evidence.py `
  --root $taskRoot `
  --training artifacts/ttt-017/attempt-04 `
  --evaluation artifacts/ttt-017/q4-04-graphs-disabled `
  --export artifacts/ttt-017/export-04 `
  --corpus artifacts/ttt-017/corpus-v4 `
  --comparison artifacts/ttt-017/comparison-04-graphs-disabled `
  --human-ratings artifacts/ttt-017/human-ratings-04.json `
  --data-card docs/evidence/ttt-017/corpus-v4-data-card.md `
  --native-checkpoint artifacts/ttt-017/admitted-native/model.safetensors `
  --output artifacts/ttt-017/final-04 `
  --semantic-source f152cafc59bda5207b8cb1c5ef7d6d60133d1b41 `
  --reporter-source ba904aad3c6640b524960f5c2a61dd8b4bc330d9
```

The actual human file must exist first. If output already exists, verify it; do
not overwrite it. The reporter source is separately bound from the Q4 transport
and training semantics, even where commits coincide. It stages evidence and
requires the original strict verifier with actual bound binaries available.
Copy only small final evidence/cards/report into Git; preserve relative paths
or rebuild a portable package deliberately rather than copying a manifest to
a new location and assuming its references changed. No weight publication.

Then update README/cards/report around the actual outcome, self-review the
follow-up PR, run required checks, observe green CI, merge and verify #41 closes.
Keep #43's remaining controller GPU integration scope separate; this historical
helper run does not validate the new controller end to end. Mark the training
goal complete only after genuine ADMITTED readback and required Git workflow.

## Validation and caveats

374 tests passed, two skips (optional Concordia and Linux /proc-specific test
on Windows); Ruff lint/format and strict mypy pass on native Windows and Linux
type targets. Replay tests use all actual frozen and long-session model actions
from the native and both Q4 phases. Windows completion flushing/platform API
compatibility fixes were required for checks on newly merged controller code.

The same Q4 bytes received two frozen readouts under different runtime settings.
Disclose that repeated evaluation; no frozen output entered training. The timing
improvement is measured, but graph capture is not isolated causally from cache/
startup effects. Synthetic English abstract worlds, overlapping generator/style
families, scripted teachers and small human samples limit generalization.
The initial TTT-016 negative result and all failed attempts remain unchanged.
