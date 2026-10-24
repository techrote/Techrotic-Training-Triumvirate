# Provenance, licensing, and reproducibility

## Run identity

Every corpus generation, evaluation, and training run should emit a machine-readable manifest containing applicable fields:

- run ID;
- git commit;
- schema/protocol versions;
- dependency lock/hash;
- random seeds;
- generator configuration;
- teacher/student model identifiers and immutable checkpoint hashes/revisions;
- prompt/template versions;
- decoding settings;
- dataset inputs and hashes;
- split manifest;
- hardware/runtime;
- command line/config;
- start/end timestamps;
- output artifact hashes;
- parent run IDs.

## Deterministic replay

World Authority and scenario generation must be replayable from version + seed/config. If exact external-model output cannot be reproduced, store its admitted response or content hash plus all available generation metadata and distinguish replay from regeneration.

## Source classes

Record provenance for:
- hand-authored data;
- deterministic generated data;
- third-party datasets;
- third-party model outputs;
- game-derived traces;
- student-generated rollouts;
- repaired/filtered derivatives.

## Licensing gate

Before a new source enters an admitted corpus, record:
- source URL/repository/model;
- version/revision;
- license;
- redistribution status;
- derivative/training-use interpretation used by the project;
- whether raw source/output may be committed;
- attribution requirements;
- reviewer/date.

If uncertain, quarantine it from admitted datasets until resolved.

## No hidden live dependencies

Default tests and corpus validators must not silently call remote APIs. Live generation is an explicit command/run mode and produces a manifest.

## Dataset identity

TTT-007 emits deterministic JSONL shards plus a canonical manifest. The manifest
records tier, scenario-family, persona and error distributions; operational command
and persona/communication content composition; teacher contribution; rejection reasons;
split identities; and per-shard SHA-256 hashes. Identical admitted
inputs, configuration and seed therefore produce identical shard and manifest content.

Unadmitted external/model-generated sources are quarantined. For source classes such
as teacher/model output, third-party datasets and game-derived traces, admission
requires both an explicit license identifier and an admitted/compatible
`license_disposition` in source metadata.

An admitted dataset version should be content-addressable or accompanied by a deterministic manifest listing shard/file hashes and counts. Record:
- tier composition;
- scenario-family distribution;
- persona distribution;
- error/recovery distribution;
- teacher contribution;
- filter/rejection counts;
- train/dev/eval separation.

## Model artifacts

For trained models record:
- base checkpoint identity;
- tokenizer identity;
- adapter/full-weight format;
- training config;
- exact dataset identity;
- export/quantization config;
- parity checks;
- benchmark report.

Large binaries need not live in git; manifests and immutable external references do.

## Evidence discipline

Do not report an expensive run as successful based only on a console summary. Preserve machine-readable metrics/results and enough immutable evidence to independently read back the claimed result.

## Session recording evidence

TTT-005 session recordings bind semantic turns to:

- session ID and run ID;
- `ttt.session_recording` schema version;
- `ttt-session-v1` protocol identity;
- scenario generator identity/seed and initial world reference;
- canonical command/action/result/event/observation content hashes;
- explicit branch parent ID, turn and parent semantic hash;
- final authoritative world hash.

LangGraph thread/checkpoint IDs may be retained as supplementary orchestration references, but they are deliberately excluded from semantic identity. Two runs with different checkpoint IDs must still compare equal when their TTT semantic records are equal.

Readback verification is fail-closed: altered stored hashes, broken delta reconstruction, scenario regeneration drift, turn discontinuity, or replay hash mismatch are errors rather than best-effort warnings.

## Corrective rollout evidence

TTT-010 records student-visited repairs as `student-generated-rollout`
`SourceProvenance` plus a `RunManifest`. The evidence binds:

- student policy ID, adapter ID and revision;
- deterministic correction-oracle identity;
- failure category/code and student attempt identity;
- iteration number and optional parent corrective-run ID;
- canonical TTT parent branch ID and parent turn hash;
- corrected episode/session semantic hashes and corpus-manifest hash;
- the LangGraph correction checkpoint as supplementary orchestration metadata.

The corrected TTT branch/episode remains authoritative corpus identity. LangGraph
checkpoint IDs do not enter the model-visible recovery input or semantic hashes, so
separate orchestration instances may produce different checkpoint IDs while retaining
the same TTT correction and corpus identities.

The original failed branch is retained and independently readable. Alternative
corrections from one historical state are separate TTT branches with distinct branch
identities and provenance; iterative corrective rounds link through `parent_run_ids`
instead of overwriting earlier evidence.

