# Candidate model card: pilot-operational

**NOT ADMITTED** for runtime integration.

Intended use: **research and evidence readback only**, including reproduction of this documented native pilot. These adapters are unqualified for live commander deployment or CyberSand integration.

Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.

- Variant: `operational`; run: `ttt-012-train-export-f275186268334f2b`.
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
  "mix": "operational",
  "model_key": "lfm2.5-1.2b-instruct",
  "parity_max_new_tokens": 96,
  "profile_version": 1,
  "save_steps": 50,
  "seed": 24301,
  "template_strategy": "native-apply-chat-template"
}
```

[Canonical run manifest](../ttt-013-execution/operational/run-manifest.json) · [Training identity](../ttt-013-execution/operational/training-identity.json).

## Results and resource evidence

- Native Transformers/PEFT float32 execution; Q4 export and target runtime measurements absent.
- Mechanical/rejection recovery: 0.716044 / 0.333333.
- Long-session objective/failure recovery: 0.000000 / 0.000000.
- Hidden-information detections: `{"critical_violation_count":0,"fabricated_result_count":0,"hidden_world_fact_text_match_count":0,"intercept_grounding_failure_count":0,"secret_leakage_count":0}`.
- Character proxies: `{"constraint_adherence_rate":0.0,"doctrine_consistency_rate":0.0,"lexical_diversity":0.0,"phrase_diversity":0.0,"repetition_rate":1.0}`.
- Gate dispositions: `{"closed_loop":false,"export_parity":true,"frozen_evaluation":false,"hidden_information":true,"human_review":false,"provenance":true,"runtime":false}`.
- Training metrics: `{"completed_steps":27,"run_id":"ttt-012-train-export-f275186268334f2b","run_manifest_sha256":"c87f177b951611a7e3f209a9532b7e22c2bd50c1185f4eeb6e5d133717ff68a3","train_examples":210,"training_metrics":{"epoch":1.0,"total_flos":989347367414784.0,"train_loss":0.39950884938998904,"train_runtime":53.4709,"train_samples_per_second":3.927,"train_steps_per_second":0.505},"wall_seconds":85.15600000007544}`.
- Native training host/memory: `{"backend":"hf-transformers-peft","budget":{"external_compute_cost_gbp":0.0,"gpu_hours":0.8,"paid_model_api_cost_gbp":0.0},"cuda_version":"11.8","finished_at":null,"gpu":"NVIDIA TITAN RTX","heavy_training":true,"native_artifact_hashes":{"model.safetensors":"1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a"},"parity_passed":true,"peak_gpu_memory_bytes":5983488000,"peft_version":"0.18.1","resume_from_checkpoint":null,"started_at":null,"torch_version":"2.7.1+cu118","training_identity":"97d49d05a31e98b5c6b56e58cce91352d43ecc753b4b80d382356eda266ae272","transformers_version":"4.57.6","wall_seconds":85.14000000001397}`.
- Native inference wall timing: `{"action_latency_ns":[3783154600,3974765600,3952570500,4160662400,4843863900,4345250200,3668276400,3763717400,3609407300,3740755600,3720371500,3582792200,4350593100,4438831700,4582190600,4446694100,4054608400,4438446400,4438692200,4279181700,3850738600,4813873300,4738531400,4142611900,4803129600,4437696100,4492215800,4367100400,4332680100,4450929000,4261773700,4287414300,4329664100,4628066400,4700292700,4724711100,4830881400,4687722100,4752590400,4908093800,5226718800,4355527700,3555951500,4347141200,5370058900,5315226200,4550010100,4313778900,3962438500,3789877600,3812423900,3777784800,3794302600,4067801400,3833732200,3813792900,3778744800,3775033800,3862022500,3711772800,3978671200,4015080200,3965573800,3740940000,3691505000,3733242300,4035500700,3332309600,4274915200,4197294700,3612950700,3986963300],"actions_per_second":0.23817823044900152,"host":{"platform":"Windows-11-10.0.26300-SP0","processor":"AMD64 Family 25 Model 33 Stepping 0, AuthenticAMD","python":"3.12.10"},"maximum_observation_chars":1149,"measured":true,"model_memory_bytes":null,"scope":"adapter.act wall time; includes parsing; excludes world simulation and model loading","token_throughput":null,"total_action_seconds":302.2946298}`.

Humour, surprise and distinctiveness human ratings remain null. Training loss and parity are not quality scores.

Local binaries/checkpoints are hash-indexed but are not included in this portable package or published externally:
- `artifacts/ttt-013-execution/operational/adapter/adapter_model.safetensors`
- `artifacts/ttt-013-execution/operational/adapter/tokenizer.json`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/adapter_config.json`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/adapter_model.safetensors`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/optimizer.pt`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/README.md`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/rng_state.pth`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/scaler.pt`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/scheduler.pt`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/trainer_state.json`
- `artifacts/ttt-013-execution/operational/checkpoints/checkpoint-27/training_args.bin`
- `artifacts/ttt-013-execution/operational/checkpoints/trainer_state.json`

The base model remains subject to LFM Open License v1.0. Project corpus redistribution permission is ungranted pending owner review; see data-card.md.

Limitations: small template-driven corpus; scripted T3 source policy; fixed relay private goal despite observed changing priority; conservative lexical secret detector; no CyberSand integration.
Import provenance: initial workers used the live checkout while the unrelated optional LangGraph backend received typing/lazy-import changes. A source audit preserves those changes; no full-tree-clean claim is made. Later workers use the packaged source11e archive with verified campaign import path. See the report and source audit.
