# Evaluation and admission

## Evaluation axes

### Mechanical command competence
Measure:
- parse/schema validity;
- correct entity reference;
- valid tool/op selection;
- capability/precondition compliance;
- successful correction after rejection;
- duplicate/conflicting command rate.

### Closed-loop task competence
Measure:
- objective completion;
- resource efficiency;
- survival/losses where applicable;
- unnecessary churn;
- recovery after execution failure;
- adaptation to changed goals and stale observations.

### Hidden-information discipline
Measure:
- secret leakage to player-visible communication;
- use of hidden world facts not present in commander observation;
- fabricated acknowledgements/results;
- player-intercept over-disclosure.

### Character quality
Automatable proxies may measure repetition, persona constraint adherence, lexical diversity, doctrine/codeword consistency, and degeneration. Human evaluation is still needed for humour, surprise, distinctiveness, and whether irrationality feels intentional rather than broken.

### Runtime properties
Measure model size, context requirement, latency/throughput on target hardware, memory, structured-output reliability, and quantization degradation.

## Required baselines

At minimum compare:
- deterministic/scripted commander;
- prompt-only candidate student;
- operational-only fine-tune;
- persona-only fine-tune;
- joint fine-tune;
- joint fine-tune plus corrective/student-visited data.

Not every release must train every baseline, but the benchmark harness must support them.

## Frozen tests

Maintain two independent evaluation classes:
- generated frozen seeds/world families excluded from training;
- handwritten/adversarial episodes targeting failure modes.

A benchmark version is immutable once used for a reported admission. New cases create a new version.

## Admission gates

Before selecting a model cast:
- corpus schema stable enough for probes;
- command protocol available;
- evaluation harness can score structured output and leakage;
- licenses/redistribution constraints recorded.

Before a pilot training run:
- selected model/checkpoint hashes recorded;
- exact dataset manifest/splits recorded;
- training config and budget recorded;
- smoke train/export/inference parity test passes.

Before a runtime candidate is admitted:
- frozen mechanical/recovery benchmarks pass declared thresholds;
- no critical hidden-information leakage cases;
- closed-loop benchmark completed;
- runtime resource target measured;
- model/data cards and provenance complete.

Thresholds should be set in the relevant issue before observing final candidate results where feasible.

## Failure corpus

Evaluation failures are not automatically training data. Promote a failure into a corrective corpus only through the versioned rollout/corpus process, and never contaminate frozen evaluation cases.

## Reporting

Every comparative report must distinguish:
- model/checkpoint;
- decoding settings;
- adapter/template;
- dataset/version;
- benchmark/version;
- hardware/runtime;
- quantization;
- stochastic seeds.

## Implemented frozen benchmark contract (TTT-009)

The first model-agnostic evaluation surface lives under
`techrotic_training_triumvirate.evaluation`.

### Adapter boundary

`StudentAdapter` exposes a stable policy identity, a per-case reset hook and
`act(EvaluationContext) -> AssistantAction`. The context contains only the
admitted commander observation, authoritative feedback/events visible to the
commander, and the benchmark persona. It does **not** reveal the adversarial
case kind or evaluator-only labels.

Deterministic baselines implement the same adapter boundary as later model
runtimes. Because TTT-005 is available, each context also carries the canonical
structured and compact observation surfaces produced by its replaceable
`SessionRenderer`; TTT-009 does not define a second rendering/session format.

### Frozen benchmark v1

The packaged manifest `benchmark_v1.json` has:

- benchmark ID `ttt-core-frozen`;
- benchmark version `1`;
- canonical manifest content hash
  `22a93e8861e25d1b6b15fea298431b4023b28610884d1699d447cf8a85bb92aa`;
- three generated reserved scenario family/seed cases;
- handwritten/adversarial cases for malformed commands, capability mismatch,
  delayed execution failure, stale observations, conflicting orders, changed
  objectives, secret leakage, fabricated results, intercept over-disclosure,
  and repetition/degeneration.

`load_benchmark_v1()` verifies the committed content hash, exact field set,
unique case identities and exact reservation coverage. Any changed v1 content
without an explicit new benchmark version/hash fails closed.

### Training/corrective-corpus guard

`frozen_evaluation_guard()` returns the exact family/seed reservation set.
TTT-007 corpus admission and TTT-010 corrective rollout code must call
`assert_training_allowed(family=..., seed=...)` before admitting generated
or student-visited cases. Frozen evaluation failures are evaluation evidence
only; they are not eligible training examples under the same family/seed
identity.

### Metrics and reporting

The CPU-small runner scores mechanical command competence, closed-loop task and
recovery competence, and hidden-information discipline against the deterministic
World Authority. It also verifies that ordinary player intercepts remain
grounded to real dispatch events and do not disclose forbidden values.

Reports bind benchmark ID/version/hash, caller-supplied code revision and
`PolicyIdentity`. Canonical JSON produces a deterministic report hash for a
deterministic adapter.

Operational metrics are separate from character metrics. Automated character
proxies cover persona-constraint adherence, repetition, lexical/phrase
diversity and doctrine/codeword consistency. Humour, surprise, distinctiveness,
and whether irrationality feels intentional remain explicitly human-evaluation
questions.

The default benchmark path has no model, network, GPU or optional Concordia
dependency.

