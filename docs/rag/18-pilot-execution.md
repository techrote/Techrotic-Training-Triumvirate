# TTT-013E bounded native pilot execution

The 2026-10-24 request to complete this repository admits the local execution
allocation `task-2026-10-24-ttt013e`. The actual hostname, GPU UUIDs, driver,
platform and Python are captured before execution in `campaign.json`. This
allocation uses one local GPU at a time. The machine exposes a Tesla V100 16 GB
and a TITAN RTX 24 GB; the execution command selects one explicitly.

The existing programme ceiling remains 24 GPU-hours, £75 external compute
across TTT-012/013 and £0 paid APIs. This allocation authorizes **£0 external
compute and £0 APIs**. The default command requests four GPU-hours including
the prompt-only comparison and all four trained candidates. This is an admitted
capacity ceiling, not a claim about actual consumption.

`scripts/run_pilot_campaign.py` builds actual World Authority episodes using
unreserved seeds, then runs `operational`, `persona`, `joint` and
`joint+corrective` against the same admitted native LFM checkpoint, seed and
versioned profile. The corpus contains T1 scripted operational episodes, T2
accepted deterministic local style-template teacher enrichments, and T3
scripted student-visited command failures followed by authoritative correction.
The template teacher has explicit repository-authored provenance; no Sprocket,
Qwen, API generation or third-party corpus contribution is claimed. This is a
limitation of the initial pilot, preserved in the source metadata.
Local generated source material uses `LicenseRef-Project-Internal-Research`:
owner-authorized research training is admitted, while redistribution rights
remain ungranted pending an owner license review. The repository has no license
file, so this execution does not invent an MIT or other public license grant.
The corpus preserves canonical source episodes, provenance and enrichments in
`source-episodes.jsonl`, whose SHA-256 is bound into its manifest.

The corpus varies scenario complexity from one to five and preserves the
assembler's scenario-family split boundary. It never relabels benchmark worlds
or moves frozen examples into training. The manifest records exact counts,
rejections, shard hashes, teacher contributions and the frozen benchmark guard.
The corpus identity and all resolved profiles are bound into the campaign plan.

The actual execution environment is a private `.venv-training` with pinned
PyTorch 2.7.1 CUDA 11.8, Transformers 4.57.6, PEFT 0.18.1, Accelerate 1.12.0 and
Safetensors 0.7.0. CUDA 11.8 retains V100/TITAN support. The complete installed
dependency set is captured with the executing interpreter's `pip freeze`.
Heavy imports and downloads remain outside default CI. The native checkpoint's
SHA-256 is verified against model-cast admission before loading it.

Each isolated worker receives one fifth of the requested time cap. The four
training workers use FP32 base weights with FP16 mixed precision, gradient
checkpointing, the native chat template and assistant-only labels. Export
parity uses FP32 greedy inference both before and after adapter reload. The
prompt-only worker loads the same immutable base without an adapter.

Every produced real candidate runs the entire TTT-009 frozen benchmark and the
TTT-014 closed-loop suite. Raw generations, parsed actions, failures, training
metrics, adapter hashes, parity and benchmark reports are retained. Malformed
model output becomes an explicit invalid command that World Authority rejects;
the adapter cannot substitute a scripted successful action. Training loss and
serialization parity do not establish runtime quality.

The campaign reserves each worker's complete cap before launch and reconciles
it to elapsed single-GPU wall time after the worker exits. Uncertain interrupted
reservations remain fully charged. Both the supervisor timeout and a worker
watchdog enforce the cap; a persistent exclusive lock prevents concurrent
execution against the same budget ledger. A stale lock requires verifying its
recorded process stopped before manual removal. Resume refuses changed
model/data/profile/seed/source/allocation identity, verifies existing artifact
hashes and uses only checkpoints under the original run directory.

Example execution after committing the implementation sources:

```powershell
.\.venv-training\Scripts\python.exe scripts/run_pilot_campaign.py `
  --corpus artifacts/pilot-corpus-v2 --output artifacts/ttt-013-execution `
  --prepare-corpus --allocation-id task-2026-10-24-ttt013e `
  --git-commit COMMITTED_SOURCE_SHA --gpu-hours 4 --gpu-index 0 --allow-heavy
```

Only `campaign.json` with all five variants complete and verified reports
establishes completed execution. Failed workers and incomplete campaigns are
preserved as evidence and cannot be reported as four successful fine-tunes.
The final runtime decision uses the prospective gates in
`19-final-admission.md`; negative results are valid evidence.
