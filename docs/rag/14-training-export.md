# TTT-012 training, export, and inference parity

## Contents

1. Source of truth — admitted model and profile resolution.
2. Corpus mapping — semantic chat conversion and assistant-only labels.
3. Fine-tuning backend — opt-in native-checkpoint PEFT LoRA execution.
4. Reproducibility — dataset identity, seeded order, checkpoints, and resume.
5. Smoke training — CPU-small deterministic CI path.
6. Export and parity — artifact provenance and fixed-fixture reload checks.
7. Quantization — explicit optional GGUF/Q4 contract.
8. CLI and dataset mixes — operational usage.
9. Budget and non-goals — expensive-work refusal.

## 1. Source of truth

TTT-012 does not repeat model repository names, checkpoint revisions, native
artifact hashes, or runtime GGUF identities in executable training code.

`resolve_model_binding()` reads the authoritative TTT-011
`model_cast_v1.json` admission. The versioned
`training/profiles_v1.json` document contains only the training choices that
are genuinely TTT-012 configuration: backend, LoRA method/hyperparameters,
sequence limit, template strategy, checkpoint interval, and optional
quantization target.

The admitted students are:

- primary: the model named by `roles.primary_compact_student`;
- challenger: the first model named by `roles.challenger_students`.

Both currently use native checkpoint training with
`hf-transformers-peft` + LoRA. A changed cast must therefore be reconciled
through the admission/config documents rather than hidden Python constants.

## 2. Corpus mapping

TTT-007 `CorpusExample` records are projected into semantic chat messages.
The model prompt contains:

- admitted commander observation;
- commander-private context;
- persona;
- accepted teacher enrichment where present;
- for corrective examples, the failed prior student action plus authoritative
  interpreter/world feedback.

The assistant target contains **only**:

- TTT command envelopes;
- TTT communication records.

`validate_assistant_target()` refuses authoritative interpreter results,
world events, observations, evaluation annotations, player records, or other
environment-owned records in the supervised target.

The HF backend delegates final role/token rendering to the selected tokenizer's
native `apply_chat_template`. It verifies that the full sequence preserves the
generation-prefix boundary, then masks every prompt token with `-100`; only
assistant target tokens contribute to causal-LM loss.

## 3. Fine-tuning backend

Heavy training is implemented by `run_hf_peft_training()` and imported only
after explicit execution admission. The default project install therefore
remains lightweight.

The backend:

1. resolves the admitted native repository/revision;
2. loads that exact tokenizer and causal-LM checkpoint;
3. applies the native chat template;
4. creates PEFT LoRA adapters using the versioned TTT profile;
5. uses explicit training/data seeds;
6. checkpoints through Transformers Trainer;
7. supports `resume_from_checkpoint`;
8. exports adapter + tokenizer state;
9. reloads the exported adapter on the same immutable base revision; and
10. performs deterministic fixed-fixture pre/post-export inference parity.

The selected profile uses `all-linear` LoRA targeting so architecture-specific
projection names are not scattered through TTT code.

## 4. Reproducibility

`load_corpus_examples()` requires a TTT-007 corpus directory with
`manifest.json` and verifies every recorded shard SHA-256 before reading it.
Frozen-evaluation shards are never loaded into training.

`DatasetIdentity` binds:

- the exact manifest-file SHA-256;
- deterministic training-visible dataset content hash;
- every recorded shard name/SHA-256;
- split identities from the corpus manifest.

The tiny checkpoint and heavy run manifest additionally bind:

- model-cast content hash;
- native model revision/artifact identity;
- training-profile contents;
- dataset mix;
- training seed;
- command line;
- git commit;
- output artifact hashes;
- budget admission for heavy runs.

A resume checkpoint whose training identity, dataset identity, model identity,
or seeded example order differs is refused.

## 5. Smoke training

Default CI must not download LFM/Qwen weights. TTT-012 therefore includes
`tiny-deterministic-v1`, a local exact-match model used to exercise the
training control plane end to end.

It verifies:

- deterministic seeded training order;
- train/dev separation;
- checkpoint serialization;
- interruption and exact resume;
- model/config/dataset identity refusal;
- export metadata;
- artifact hashes;
- pre/post-export inference parity.

The tiny backend is **not** evidence about model quality and must not be
reported as an LFM/Qwen fine-tuning result.

## 6. Export and parity

Every smoke export contains:

- `adapter.json`;
- tokenizer/template provenance;
- resolved model binding;
- exact training configuration;
- exact dataset identity;
- parity evidence;
- optional quantization specification;
- canonical `ttt.run_manifest`;
- `export-manifest.json` with artifact hashes.

The heavyweight PEFT path saves the real adapter/tokenizer, records per-file
hashes, reloads the saved adapter, and compares fixed greedy outputs against the
in-memory trained adapter before declaring parity.

Parity proves serialization/inference-format consistency. It does not replace
TTT-009 frozen evaluation or TTT-013 pilot quality gates.

## 7. Quantization

The admitted local runtime targets use Q4_K_M GGUF artifacts, so TTT-012 records
an optional quantization/export specification.

Quantization remains disabled by default and binds:

- GGUF format;
- Q4_K_M target;
- the TTT-011 pinned llama.cpp revision;
- the admitted reference inference-artifact SHA-256;
- required pre/post-export format parity;
- later frozen-benchmark quality comparison.

TTT-012 does not silently quantize or substitute the existing GGUF for the
native training checkpoint.

## 8. CLI and dataset mixes

Install normal development dependencies for the deterministic path:

```bash
python -m pip install -e ".[dev]"
```

Inspect the admitted primary profile:

```bash
ttt-train profile --model primary --mix joint+corrective --seed 24301
```

Run CPU-small smoke training/export/parity:

```bash
ttt-train smoke \
  --model primary \
  --mix joint+corrective \
  --seed 24301 \
  --output build/ttt-012-smoke \
  --git-commit "$(git rev-parse HEAD)"
```

Supported mix semantics:

- `operational` — command targets only;
- `persona` — communication targets only;
- `joint` — commands + communications, excluding corrective examples;
- `joint+corrective` — joint targets plus T3/recovery examples.

For the opt-in native-model path:

```bash
python -m pip install -e ".[dev,training]"

ttt-train train-hf \
  --corpus artifacts/corpus-v1 \
  --output artifacts/ttt-012-run \
  --model primary \
  --mix joint+corrective \
  --seed 24301 \
  --gpu-hours 1 \
  --external-cost-gbp 10 \
  --allow-heavy \
  --git-commit "$(git rev-parse HEAD)"
```

The same command can use `--model challenger`. Resume requires the explicit
`--resume-from-checkpoint PATH` and still revalidates model/config/dataset
identity at the TTT layer where applicable.

## 9. Budget and non-goals

Heavy execution refuses unless `--allow-heavy` is explicit and the request is
within the TTT-011 TTT-012 envelope:

- at most 3 GPU-hours;
- external compute cost no greater than the recorded £75 shared initial
  envelope;
- £0 paid model/API spend.

Default CI performs no heavyweight checkpoint download, GPU initialization,
substantial training, GGUF conversion, corpus generation, or TTT-013 pilot
experiment.

TTT-013 owns pilot quality experiments and consumption of the larger admitted
training budget.

## Native training identity v2

New native HF training writes `training-identity.json` with schema version 2.
Its identity hash covers admitted model binding, complete training configuration,
exact dataset identity, backend and full immutable `source_revision`. An existing
identity must exactly match before an interrupted checkpoint can resume, and
these checks run before any heavyweight model/runtime import. Unknown/malformed
versions, extra fields and source drift refuse.

Interrupted identity-v1 checkpoints do not bind source and are explicitly refused.
A completed historical v1 output remains independently verifiable using its
canonical RunManifest, which binds the original source commit, plus matching
model/data/config identity, artifact inventory/hashes and parity. That readback
does not authorize restarting old training under different source. New v2
completed outputs receive the same source-bearing manifest checks.

New native training/evaluation requires `CUDA_VISIBLE_DEVICES` to name one full
physical GPU UUID. Actual CUDA device UUID is checked before loading weights;
selected/actual UUID and name are recorded. This avoids ordinal changes silently
selecting another GPU. The current local allocation permits only the TITAN RTX
UUID documented in `18-pilot-execution.md`. Export artifact inventory paths use
forward slashes for portable JSON manifests. Existing historical backslash paths
remain readable after containment validation.
