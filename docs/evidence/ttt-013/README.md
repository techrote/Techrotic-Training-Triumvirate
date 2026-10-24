# TTT-013 preparation evidence

Historical status at preparation merge: **prepared; substantive ablation campaign
not executed by this merge**.

The later substantive TTT-013E campaign is complete in
[the actual execution evidence](../ttt-013-execution/README.md) and
[PR #39](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/39).
It produced four real native-checkpoint LoRA variants plus a prompt-only
comparison, with 745 completed model actions across the frozen and 24-turn
suites. All completed candidates used the TITAN RTX; the conservative total
charge was 0.962306 GPU-hours including preflight and the archived failed V100
attempt, with £0 external compute and £0 paid APIs.

The final programme outcome through
[PR #40](https://github.com/techrote/Techrotic-Training-Triumvirate/pull/40) is
**NOT ADMITTED**, as recorded in the
[comparative report](../ttt-016/report.md) and
[admission package](../ttt-016/admission-package.json). Human ratings remain
unfilled and trained-candidate Q4 runtime qualification is not claimed. This
directory preserves the earlier preparation history and smoke boundary rather
than substituting that smoke output for the later real evidence.

Issue #14 permits a preparation-only completion when the admitted
budget/configuration does not supply enough execution admission to run the real
fine-tunes. TTT-011 recorded a 24 GPU-hour / £75 / £0-API ceiling, but at that
preparation merge the repository recorded no admitted TTT-013 GPU execution host
or allocation ID.

This merge therefore provides:

- fail-closed pilot corpus admission requiring T1/T2/T3 and zero frozen
  benchmark examples;
- exact TTT-009 guard binding;
- a content-addressed four-variant pilot plan;
- TTT-013-specific budget validation;
- deterministic four-way tiny-backend smoke orchestration;
- export/parity evidence for each smoke variant;
- explicit machine-readable fields preventing smoke results from being
  mistaken for model-quality evidence.

This preparation merge claimed no LFM2.5/Qwen fine-tune, GPU consumption or
TTT-009 candidate evaluation. Later actual execution is linked above and does
not change what the preparation evidence established.

The substantive four-way campaign required a named compute host/allocation and
a real pilot corpus supplied to `ttt-train pilot-plan`; TTT-013E subsequently
recorded that allocation and preserved the resulting corpus, adapters and reports.
