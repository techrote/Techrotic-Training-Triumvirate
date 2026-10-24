# TTT-013 preparation evidence

Status: **prepared; substantive ablation campaign not executed**.

Issue #14 permits a preparation-only completion when the admitted
budget/configuration does not supply enough execution admission to run the real
fine-tunes. TTT-011 records a 24 GPU-hour / £75 / £0-API ceiling, but the current
repository records no admitted TTT-013 GPU execution host or allocation ID.

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

No LFM2.5/Qwen fine-tune is claimed to have run, no GPU budget is claimed as
spent, and no TTT-009 candidate evaluation is fabricated.

The substantive four-way campaign becomes executable only after a named compute
host/allocation is admitted and the real pilot corpus is supplied to
`ttt-train pilot-plan`.
