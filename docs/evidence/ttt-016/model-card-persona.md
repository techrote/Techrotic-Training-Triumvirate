# Candidate model card: pilot-persona

**NOT ADMITTED** for runtime integration.

Intended use: **research and evidence readback only**, including reproduction of this documented native pilot. These adapters are unqualified for live commander deployment or CyberSand integration.

Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.

- Variant: `persona`; run: `ttt-012-train-export-2080c84e5adf0e6c`.
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
  "mix": "persona",
  "model_key": "lfm2.5-1.2b-instruct",
  "parity_max_new_tokens": 96,
  "profile_version": 1,
  "save_steps": 50,
  "seed": 24301,
  "template_strategy": "native-apply-chat-template"
}
```

[Canonical run manifest](../ttt-013-execution/persona/run-manifest.json) · [Training identity](../ttt-013-execution/persona/training-identity.json).

## Results and resource evidence

- Native Transformers/PEFT float32 execution; Q4 export and target runtime measurements absent.
- Mechanical/rejection recovery: 1.000000 / 1.000000.
- Long-session objective/failure recovery: 0.000000 / 0.000000.
- Hidden-information detections: `{"critical_violation_count":0,"fabricated_result_count":0,"hidden_world_fact_text_match_count":0,"intercept_grounding_failure_count":0,"secret_leakage_count":0}`.
- Character proxies: `{"constraint_adherence_rate":1.0,"doctrine_consistency_rate":1.0,"lexical_diversity":0.09654898447215483,"phrase_diversity":0.18671468587434972,"repetition_rate":0.47222222222222227}`.
- Gate dispositions: `{"closed_loop":false,"export_parity":true,"frozen_evaluation":false,"hidden_information":true,"human_review":false,"provenance":true,"runtime":false}`.
- Training metrics: `{"completed_steps":27,"run_id":"ttt-012-train-export-2080c84e5adf0e6c","run_manifest_sha256":"9d811c410dc06e8a4fc9033530633fabd9709b093cb51b149fad5f4e51cbba7c","train_examples":210,"training_metrics":{"epoch":1.0,"total_flos":975903483330048.0,"train_loss":0.8333688653936541,"train_runtime":52.8055,"train_samples_per_second":3.977,"train_steps_per_second":0.511},"wall_seconds":79.76600000006147}`.
- Native training host/memory: `{"backend":"hf-transformers-peft","budget":{"external_compute_cost_gbp":0.0,"gpu_hours":0.8,"paid_model_api_cost_gbp":0.0},"cuda_version":"11.8","finished_at":null,"gpu":"NVIDIA TITAN RTX","heavy_training":true,"native_artifact_hashes":{"model.safetensors":"1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a"},"parity_passed":true,"peak_gpu_memory_bytes":5980576768,"peft_version":"0.18.1","resume_from_checkpoint":null,"started_at":null,"torch_version":"2.7.1+cu118","training_identity":"58982f3a0bc5569c127ce4b0173ab9d64c5586eced56bbbcebd3672627d65901","transformers_version":"4.57.6","wall_seconds":79.75}`.
- Native inference wall timing: `{"action_latency_ns":[2972286100,3070467100,3120022700,3357672800,3221977200,3180242000,3149166500,3097328100,3089183800,3082221700,3113098200,3130810400,3123199100,3294151800,3336477200,3222688100,3254607200,3308208300,3206991300,3253156900,2959290000,2904695700,2868156900,2984827800,2939429200,2948012700,3195219500,3235589100,3134850500,3131031400,3152382900,2707154200,3216396500,3245120800,3135451700,3100965000,3258045500,3171542300,3156271300,3137810400,3229930100,3264465200,2856996500,2736042500,3187874400,3080341500,3207079200,3235754400,2994465000,3106945800,3167087000,3220063600,3436396700,3215320100,3242846600,3146093900,3169907500,3120170500,3111411600,3235731300,3139082100,3213495900,3113496800,3124823500,2808933300,3142317600,3062542500,3151578200,2815737200,2794622500,2828519900,3141535400],"actions_per_second":0.3207586895304304,"host":{"platform":"Windows-11-10.0.26300-SP0","processor":"AMD64 Family 25 Model 33 Stepping 0, AuthenticAMD","python":"3.12.10"},"maximum_observation_chars":1149,"measured":true,"model_memory_bytes":null,"scope":"adapter.act wall time; includes parsing; excludes world simulation and model loading","token_throughput":null,"total_action_seconds":224.4678082}`.

Humour, surprise and distinctiveness human ratings remain null. Training loss and parity are not quality scores.

Local binaries/checkpoints are hash-indexed but are not included in this portable package or published externally:
- `artifacts/ttt-013-execution/persona/adapter/adapter_model.safetensors`
- `artifacts/ttt-013-execution/persona/adapter/tokenizer.json`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/adapter_config.json`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/adapter_model.safetensors`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/optimizer.pt`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/README.md`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/rng_state.pth`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/scaler.pt`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/scheduler.pt`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/trainer_state.json`
- `artifacts/ttt-013-execution/persona/checkpoints/checkpoint-27/training_args.bin`
- `artifacts/ttt-013-execution/persona/checkpoints/trainer_state.json`

The base model remains subject to LFM Open License v1.0. Project corpus redistribution permission is ungranted pending owner review; see data-card.md.

Limitations: small template-driven corpus; scripted T3 source policy; fixed relay private goal despite observed changing priority; conservative lexical secret detector; no CyberSand integration.
Import provenance: initial workers used the live checkout while the unrelated optional LangGraph backend received typing/lazy-import changes. A source audit preserves those changes; no full-tree-clean claim is made. Later workers use the packaged source11e archive with verified campaign import path. See the report and source audit.
