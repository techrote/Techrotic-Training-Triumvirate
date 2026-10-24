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

Positive decisions additionally cross-check gate booleans against their evidence:
the frozen report must cover every frozen case, its mechanical aggregates must
match case metrics, and the actual mechanical/rejection/hidden-information
thresholds must pass. Closed-loop evidence is authoritatively replayed and must
be substantive, pass objective/failure-recovery thresholds, and have zero
critical detections. All referenced evaluations must have the same complete
policy identity and source commit as the package; `candidate_id` must exactly
equal their `policy.policy_id`. A failed parity report cannot support a true
export-parity gate.

An empty blinded packet is not completed human evaluation. Evidence labelled
`human-ratings` must have schema `ttt.human_ratings`, integer `schema_version=1`,
the matching `candidate_id`, and a nonempty `ratings` array. Every rating has a
unique, nonempty `reviewer_id` and supplied integer 1–5 values for `humour`,
`surprise`, and `distinctiveness`. Null scores, empty arrays, booleans masquerading
as scores, duplicate reviewers, and ratings belonging to a different candidate
are rejected. Pseudonymous reviewer identifiers are sufficient; the verifier
cannot independently authenticate who supplied a score.

Evidence labelled `runtime-measurements` uses schema
`ttt.runtime_measurements`, integer `schema_version=1`, matching `candidate_id`,
`model_role` (`primary` or `challenger`), `quantization=Q4_K_M`, a nonempty `host`
description (hardware and runtime), and the measured artifact's
`artifact_sha256`. It requires positive integer `context_tokens`,
`artifact_size_bytes`, and `peak_resident_memory_bytes`, plus finite positive
`ttft_seconds` and `decode_tokens_per_second`. A true runtime gate is rejected
unless these measurements meet the original TTT-011 role-specific targets.
The role must resolve to the candidate's admitted `base_model` repository
(optionally followed by `@` and its exact admitted native revision), preventing
a primary candidate from borrowing the challenger's looser resource limits.
Native-LoRA timing or a descriptive text file cannot fill this gate. A verifier
can check supplied measurements and their file hashes, not independently prove
that the hardware experiment occurred.

These schemas reject unknown fields. Retain raw human packets, detailed runtime
logs, and provenance as additional hashed evidence with distinct descriptive
kinds; those artifacts do not substitute for the required scored/measurement
records. Negative packages may preserve failed measurements and unfilled packets
without claiming the corresponding gate passed.

Large model binaries remain outside Git. Artifact hashes and their actual
locations belong in the candidate cards/run manifests; unavailable external
artifacts must be listed explicitly and cannot support positive admission.
Missing human evaluation, omitted prompt-only/challenger runs and missing
quantization measurements remain explicit limitations rather than imputed scores.

The final report must cover command validity/recovery/objectives, hidden
information, repetition/persona/diversity, human ratings, runtime and export
effects separately. It records failed or partial execution and evidence-based
next experiments without feeding frozen evaluation failures back into training.
