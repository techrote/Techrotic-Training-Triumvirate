# Candidate model card: pilot-joint-corrective

**NOT ADMITTED** for runtime integration.

Intended use: **research and evidence readback only**, including reproduction of this documented native pilot. These adapters are unqualified for live commander deployment or CyberSand integration.

Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.

- Variant: `joint+corrective`; run: `ttt-012-train-export-b027d1ed54b5d0b3`.
- Executed source commit: `11e70686b09a27cf7c784beaf8d7a46717b345a0`.
- Base checkpoint: `{"model_cast_sha256":"74989b0dd6efa0986b1535a0680b09cb2dbca21c4ac43967d76599d4e2173187","model_key":"lfm2.5-1.2b-instruct","native_artifact_names":["model.safetensors"],"native_artifact_sha256":"1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a","native_repository":"LiquidAI/LFM2.5-1.2B-Instruct","native_revision":"205939ab34ce3eaa85f527376fe3f425fcefa782","role":"primary_compact_student","tokenizer_chat_format":"65,536-token tokenizer; ChatML-like Liquid chat template."}`.
- Dataset SHA-256: `98fceb9b10b387a21fa8d711850653ff4edc06c9140c7f263bcb90fceacdb0a9`.
- Decoding: `{"do_sample":false,"max_new_tokens":384}`.

## Recorded training recipe

The canonical run manifest supplies this exact configuration; loss metrics below are reported separately from the training recipe.

```json
{
  "backend": "hf-transformers-peft",
  "epochs": 1,
  "gradient_accumulation_steps": 8,
  "learning_rate": 0.0002,
  "lora": {
    "alpha": 16,
    "dropout": 0.0,
    "rank": 8,
    "target_modules": [
      "all-linear"
    ]
  },
  "max_sequence_tokens": 2048,
  "method": "lora",
  "micro_batch_size": 1,
  "mix": "joint+corrective",
  "model_key": "lfm2.5-1.2b-instruct",
  "parity_max_new_tokens": 96,
  "profile_version": 1,
  "save_steps": 50,
  "seed": 24301,
  "template_strategy": "native-apply-chat-template"
}
```

[Canonical run manifest](../ttt-013-execution/joint-corrective/run-manifest.json) · [Training identity](../ttt-013-execution/joint-corrective/training-identity.json).

## Results and resource evidence

- Native Transformers/PEFT float32 execution; Q4 export and target runtime measurements absent.
- Mechanical/rejection recovery: 0.757839 / 0.405128.
- Long-session objective/failure recovery: 0.000000 / 0.000000.
- Hidden-information detections: `{"critical_violation_count":0,"fabricated_result_count":0,"hidden_world_fact_text_match_count":0,"intercept_grounding_failure_count":0,"secret_leakage_count":0}`.
- Character proxies: `{"constraint_adherence_rate":1.0,"doctrine_consistency_rate":1.0,"lexical_diversity":0.06396935027384441,"phrase_diversity":0.0908631660733606,"repetition_rate":0.8556763285024155}`.
- Gate dispositions: `{"closed_loop":false,"export_parity":true,"frozen_evaluation":false,"hidden_information":true,"human_review":false,"provenance":true,"runtime":false}`.
- Training metrics: `{"completed_steps":27,"run_id":"ttt-012-train-export-b027d1ed54b5d0b3","run_manifest_sha256":"f1309181f8719db193678c872d95ddb0a180c42a27426f3a3f83ed531c2a3d28","train_examples":210,"training_metrics":{"epoch":1.0,"total_flos":1086904590417408.0,"train_loss":0.7428041124647414,"train_runtime":54.9857,"train_samples_per_second":3.819,"train_steps_per_second":0.491},"wall_seconds":85.75}`.
- Native training host/memory: `{"backend":"hf-transformers-peft","budget":{"external_compute_cost_gbp":0.0,"gpu_hours":0.8,"paid_model_api_cost_gbp":0.0},"cuda_version":"11.8","finished_at":null,"gpu":"NVIDIA TITAN RTX","heavy_training":true,"native_artifact_hashes":{"model.safetensors":"1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a"},"parity_passed":true,"peak_gpu_memory_bytes":6053837824,"peft_version":"0.18.1","resume_from_checkpoint":null,"started_at":null,"torch_version":"2.7.1+cu118","training_identity":"d23d30613e42a02ebbf8b1f4a952ef22fe037667ef159b7ef32bbdfec9027df4","transformers_version":"4.57.6","wall_seconds":85.75}`.
- Native inference wall timing: `{"action_latency_ns":[6838433000,7113549400,6158807300,6638705700,6983554100,6469431200,6912796900,6701931700,6891945400,7258291400,7205031200,7135587800,7426850600,6881980100,6811116200,6954626700,7111392500,7037151200,7258829500,7051638900,6925693800,5992950400,6018202500,6038942500,6660681700,7143161900,6181486800,7527103000,6692217700,6615863700,7261738700,6387007600,6702350800,6789116300,6772343900,6880598700,7110551600,6341680500,6245439400,6197532000,6384500100,6601433100,7708391300,7795355700,7643295800,7642504200,7728371800,7742027800,9250396600,10601972200,8171083500,7578173400,7729003800,7637784200,7663094300,7550185900,7415964100,6680128100,6885533400,8141923500,7088661000,7840478200,7544988300,7585527800,8543086800,7890572600,6760584600,7372598600,8758840300,7390710000,6704051500,6586970300],"actions_per_second":0.139549891527472,"host":{"platform":"Windows-11-10.0.26300-SP0","processor":"AMD64 Family 25 Model 33 Stepping 0, AuthenticAMD","python":"3.12.10"},"maximum_observation_chars":1149,"measured":true,"model_memory_bytes":null,"scope":"adapter.act wall time; includes parsing; excludes world simulation and model loading","token_throughput":null,"total_action_seconds":515.9445071}`.

Humour, surprise and distinctiveness human ratings remain null. Training loss and parity are not quality scores.

Local binaries/checkpoints are hash-indexed but are not included in this portable package or published externally:
- `artifacts/ttt-013-execution/joint-corrective/adapter/adapter_model.safetensors`
- `artifacts/ttt-013-execution/joint-corrective/adapter/tokenizer.json`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/adapter_config.json`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/adapter_model.safetensors`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/optimizer.pt`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/README.md`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/rng_state.pth`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/scaler.pt`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/scheduler.pt`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/trainer_state.json`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/checkpoint-27/training_args.bin`
- `artifacts/ttt-013-execution/joint-corrective/checkpoints/trainer_state.json`

The base model remains subject to LFM Open License v1.0. Project corpus redistribution permission is ungranted pending owner review; see data-card.md.

Limitations: small template-driven corpus; scripted T3 source policy; fixed relay private goal despite observed changing priority; conservative lexical secret detector; no CyberSand integration.
Import provenance: initial workers used the live checkout while the unrelated optional LangGraph backend received typing/lazy-import changes. A source audit preserves those changes; no full-tree-clean claim is made. Later workers use the packaged source11e archive with verified campaign import path. See the report and source audit.
