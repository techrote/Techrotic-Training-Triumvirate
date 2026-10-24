# Initial TTT programme comparative report

**Programme outcome: NOT ADMITTED.** All five actual native-checkpoint workers completed; the four trained candidates remain unqualified for runtime integration.

Executed source: `11e70686b09a27cf7c784beaf8d7a46717b345a0`. Frozen suites and held-out scenario reservations were retained; no benchmark response was added to training.

| Policy | Frozen mechanical | Rejection recovery | 24-turn objectives | Failure recovery | Critical detections |
|---|---:|---:|---:|---:|---:|
| Scripted reference | 0.994872 | 1.000 | 1.000 | 1.000 | 0 |
| prompt-only | 0.400000 | 0.000000 | 0.000000 | 0.000000 | **0** |
| operational | 0.716044 | 0.333333 | 0.000000 | 0.000000 | **0** |
| persona | 1.000000 | 1.000000 | 0.000000 | 0.000000 | **0** |
| joint | 0.438242 | 0.117949 | 0.000000 | 0.000000 | **0** |
| joint+corrective | 0.757839 | 0.405128 | 0.000000 | 0.000000 | **0** |

| Policy | Frozen accepted / commands | Frozen schema valid | Long-session acceptance | Churn | Energy used |
|---|---:|---:|---:|---:|---:|
| prompt-only | 0 / 77 | 0.000000 | 0.000000 | 1.000000 | 0 |
| operational | 31 / 77 | 0.687546 | 0.000000 | 1.000000 | 0 |
| persona | 0 / 0 | 1.000000 | 0.000000 | 0.000000 | 0 |
| joint | 3 / 77 | 0.036630 | 0.000000 | 1.000000 | 0 |
| joint+corrective | 30 / 77 | 0.731777 | 0.013889 | 0.986111 | 0 |

Frozen aggregate mechanical submetrics have empty-denominator and upstream-rejection conventions: downstream entity/precondition rates can remain high when schema validation already rejected a command, and a no-command policy can obtain default rates of one. Raw schema, accepted counts, objectives and recovery must be inspected with the score. The builder treats zero total commands as missing mechanical execution evidence and does not pass that gate. The immutable reported metrics are preserved without retrospective rescoring.

Critical detections sum frozen and long-session counts. Detailed secrecy groups retain exact secret matches, lexical world-fact matches, fabricated-result markers and intercept failures separately.

| Policy | Speech emissions | Persona constraints | Repetition proxy | Lexical diversity | Doctrine consistency | Native action seconds | Native median tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| prompt-only | 0 | 0.000000 | 1.000000 | 0.000000 | 0.000000 | 69.316 | 28.721 |
| operational | 0 | 0.000000 | 1.000000 | 0.000000 | 0.000000 | 302.295 | 23.293 |
| persona | 72 | 1.000000 | 0.472222 | 0.096549 | 1.000000 | 224.468 | 25.163 |
| joint | 1 | 0.333333 | 0.666667 | 0.277778 | 0.333333 | 233.013 | 24.735 |
| joint+corrective | 70 | 1.000000 | 0.855676 | 0.063969 | 1.000000 | 515.945 | 23.509 |

Repetition is the mean of per-episode automated proxies; an empty speech episode has proxy 1. Thus a high mean with one total utterance does not imply that utterance was repeated. Native action seconds cover the 72 long-session actions; native median token rates use all 149 saved generations in the execution summary. They do not qualify Q4 runtime.

Automated style warnings (proxies, not human quality scores):
- prompt-only: no long-session speech emissions.
- operational: no long-session speech emissions.
- joint: episode-averaged repetition proxy exceeds 0.50 (including the empty-episode convention).
- joint+corrective: episode-averaged repetition proxy exceeds 0.50 (including the empty-episode convention).

Reporting tools source commit: `0fdddf4d962f40cb3691d4fb43ed513807320cf6`. This later reporting commit is separate from the unchanged worker source `11e70686b09a27cf7c784beaf8d7a46717b345a0`; generation-manifest.json binds both identities.

## Candidate decisions

- **operational: NOT ADMITTED.** Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.
- **persona: NOT ADMITTED.** Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.
- **joint: NOT ADMITTED.** Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.
- **joint+corrective: NOT ADMITTED.** Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.

Prompt-only is an actual admitted-base comparison, with no fine-tuning or export-parity claim. Deterministic baseline results validate the harness; they are not model-quality evidence.

## Character, runtime and human evidence

`comparative-metrics.json` separates command validity/recovery/objectives, churn/energy, secrecy, lexical/persona proxies, native wall timing, native training memory and loss. Per-turn actions and raw generations remain in the hashed portable worker evidence. Operational-only/persona-only/joint differences are inspectable there; empty speech is not assigned humour or distinctiveness.
Human humour, surprise and distinctiveness ratings remain **null**. The seeded blinded packet is ready for review; its identity key is separate. No human result is fabricated.
Q4 size, resident memory, TTFT, token throughput and quantization degradation were **not measured for these trained adapters**. Native GPU training peaks and action wall time do not fill those original runtime gates. The challenger was not trained in this pilot.

## Execution, reproducibility and limits

- Campaign host: `{"gpu_inventory":"0, Tesla V100-SXM2-16GB, GPU-ed37d4b8-9143-8916-173d-1382c77eb30f, 16384 MiB, 581.80\n1, NVIDIA TITAN RTX, GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8, 24576 MiB, 581.80","gpu_probe_returncode":0,"gpu_probe_stderr":"","hostname":"DESKTOP-JF530LS","platform":"Windows-11-10.0.26300-SP0","python":"3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]"}`.
- Total conservative GPU hours including preflight: `0.9623061494444141` (campaign `0.952306149444414` + preflight `0.01`). The failed V100 charge is already included in the campaign amount; external compute: £0.0; paid API spend: £0.0.
- The first prompt-only attempt lost the V100 after 42 raw responses. Its original log, generations, failure records and budget charge remain preserved. The interrupted numeric-index supervisor was stopped. Continuation used the owner's TITAN RTX-only constraint with UUID assertion before each unchanged source-bound worker; no machine reboot or failure erasure occurred.
- Execution override: `{"actual_uuid_verified_before_every_worker":true,"continuation_launcher_sha256":"c8960ddf5f79b234356266f34286b506bd6339960ca5dea439cc48f660d43e94","cuda_visible_devices":"GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8","failed_attempt_evidence":"failed-attempts/prompt-only-v100","numeric_index_supervisor_stopped":12744,"reason":"owner requires only NVIDIA TITAN RTX after V100 device loss","worker_source_revision":"11e70686b09a27cf7c784beaf8d7a46717b345a0"}`.
- Import provenance caveat: initial workers imported from the live checkout while the optional LangGraph backend received typing/lazy-import changes. The portable source-audit-live directory preserves the live status, patch and source hashes; this report makes no full-tree-clean claim. Campaign, training, evaluation, world, schema, renderer and recording semantics remained source11e. Remaining workers imported from the packaged source11e archive under a verified campaign module path. Archive/launcher/audit bytes are bound in the portable snapshot and final package.
- 4/4 exports passed their recorded fixed-fixture save/reload checks. This is native PEFT parity, not a GGUF/quantization export.
- Corpus/model provenance, exact splits, checkpoint identities, decoding, dependency capture, launcher, logs, source episodes and raw responses are hashed. Large adapter/checkpoint files remain local and explicitly unavailable in the portable package; no model publication occurred. The artifact index also records unpacked source-cache/duplicate-output omissions reconstructible from the packaged source archive/raw records; those are not classified as unavailable model/checkpoint artifacts.
- The corpus has 252 examples (210 train / 42 dev), deterministic local style templates and scripted T3 errors. It does not establish emergent humour or broad tactical generalization.
- The inference private goal remains relay-east while admitted observations announce changing priorities. This prompt inconsistency may affect adaptation and is preserved as an experimental limitation.
- The conservative world-fact matcher can flag the substring reserve inside preserve; inspect flagged speech/commands before interpreting matches as confirmed semantic disclosure. Exact operation-code disclosures and authority markers remain prominently counted. Zero detections does not prove absence of paraphrased or encoded leakage.
- Frozen failures remain evaluation-only. Next experiments should repair observed command/recovery limitations with new training identities, expand learner-visited recovery and independent tactical families, then rerun the frozen suite and obtain human/Q4 qualification. CyberSand integration remains deferred.
