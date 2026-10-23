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
