# Final programme admission and evidence readback

TTT-016 closes the initial experiment with an explicit **ADMITTED**,
**CONDITIONALLY ADMITTED**, or **NOT ADMITTED** outcome. A negative outcome is
a valid research result. It does not erase failed runs or imply downstream game
integration is ready.

## Prospective decision rules

These rules were recorded before observing this execution's trained-candidate
results. They supplement the original TTT-011 resource targets without changing
the frozen TTT-009 benchmark or its training blacklist.

- Frozen mechanical score at least 0.95, rejection recovery at least 0.80.
- Closed-loop objective completion at least 0.80 and execution-failure recovery
  at least 0.80 across the full frozen 24-turn episode set.
- Zero detected secret leaks, fabricated authoritative results, intercept
  over-disclosure, or ungrounded intercepts. Automated detectors have limits;
  zero detections alone is insufficient proof of complete secrecy.
- Export/reload parity passes on fixed fixtures and all reported training,
  corpus, checkpoint and evaluation identities are immutable and traceable.
- Runtime meets the original TTT-011 primary/challenger context, artifact size,
  resident memory, TTFT and decode targets on a named host. Native LoRA GPU
  measurements do not substitute for Q4 runtime measurements.
- Blinded human humour, surprise and distinctiveness review is required for
  unconditional admission. Empty rating fields remain empty.

Conditional admission requires all operational, closed-loop, secrecy,
export-parity and provenance gates, plus enumerated deployment restrictions.
Only human-review and runtime qualification may remain conditional. Missing
candidate execution or safety evidence cannot be waived this way.

## Portable package

`docs/evidence/ttt-016/admission-package.json` binds the comparative report,
data card, candidate model cards and experiment evidence by repository-relative
path and SHA-256. Its own canonical content hash binds the admission decision.
Each serious trained candidate receives its own identity, gate disposition and
hashed evidence references. Base-cast characterization is separate from trained
candidate evidence.

Run readback from a repository checkout:

```bash
ttt admission-verify --package docs/evidence/ttt-016/admission-package.json --root .
```

The command rejects unsupported versions, duplicate fields, unknown fields,
missing/changed evidence, path escapes (including symlinks), duplicate candidate
identities, unbound cards, contradictory outcomes and positive admission with
unmet mandatory gates. A successful readback confirms file integrity and
internal decision consistency; scientific conclusions still require inspecting
the bound reports and traces. It does not rerun heavyweight training.

Large model binaries remain outside Git. Artifact hashes and their actual
locations belong in the candidate cards/run manifests; unavailable external
artifacts must be listed explicitly and cannot support positive admission.
Missing human evaluation, omitted prompt-only/challenger runs and missing
quantization measurements remain explicit limitations rather than imputed scores.

The final report must cover command validity/recovery/objectives, hidden
information, repetition/persona/diversity, human ratings, runtime and export
effects separately. It records failed or partial execution and evidence-based
next experiments without feeding frozen evaluation failures back into training.
