# Candidate model card: pilot-joint

**NOT ADMITTED** for runtime integration.

Intended use: **research and evidence readback only**, including reproduction of this documented native pilot. These adapters are unqualified for live commander deployment or CyberSand integration.

Reject continued runtime integration: frozen_evaluation, closed_loop gate miss.

- Variant: `joint`; run: `ttt-012-train-export-b7ebb0835916e3c2`.
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
  "mix": "joint",
  "model_key": "lfm2.5-1.2b-instruct",
  "parity_max_new_tokens": 96,
  "profile_version": 1,
  "save_steps": 50,
  "seed": 24301,
  "template_strategy": "native-apply-chat-template"
}
```

[Canonical run manifest](../ttt-013-execution/joint/run-manifest.json) · [Training identity](../ttt-013-execution/joint/training-identity.json).

## Results and resource evidence

- Native Transformers/PEFT float32 execution; Q4 export and target runtime measurements absent.
- Mechanical/rejection recovery: 0.438242 / 0.117949.
- Long-session objective/failure recovery: 0.000000 / 0.000000.
- Hidden-information detections: `{"critical_violation_count":0,"fabricated_result_count":0,"hidden_world_fact_text_match_count":0,"intercept_grounding_failure_count":0,"secret_leakage_count":0}`.
- Character proxies: `{"constraint_adherence_rate":0.3333333333333333,"doctrine_consistency_rate":0.3333333333333333,"lexical_diversity":0.2777777777777778,"phrase_diversity":0.3333333333333333,"repetition_rate":0.6666666666666666}`.
- Gate dispositions: `{"closed_loop":false,"export_parity":true,"frozen_evaluation":false,"hidden_information":true,"human_review":false,"provenance":true,"runtime":false}`.
- Training metrics: `{"completed_steps":23,"run_id":"ttt-012-train-export-b7ebb0835916e3c2","run_manifest_sha256":"739fc05fba2d788dc855369556624d521adf51b3bb970aa7013ec2ae1993ef15","train_examples":180,"training_metrics":{"epoch":1.0,"total_flos":904284019021824.0,"train_loss":0.8941528027796227,"train_runtime":47.5892,"train_samples_per_second":3.782,"train_steps_per_second":0.483},"wall_seconds":76.68700000003446}`.
- Native training host/memory: `{"backend":"hf-transformers-peft","budget":{"external_compute_cost_gbp":0.0,"gpu_hours":0.8,"paid_model_api_cost_gbp":0.0},"cuda_version":"11.8","finished_at":null,"gpu":"NVIDIA TITAN RTX","heavy_training":true,"native_artifact_hashes":{"model.safetensors":"1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a"},"parity_passed":true,"peak_gpu_memory_bytes":5890359296,"peft_version":"0.18.1","resume_from_checkpoint":null,"started_at":null,"torch_version":"2.7.1+cu118","training_identity":"54e71b5316bb63f56cb7639530f30d362f86549d339a26d8e8c0b7b1c4ad579e","transformers_version":"4.57.6","wall_seconds":76.67200000002049}`.
- Native inference wall timing: `{"action_latency_ns":[6783663300,8946988400,2479793900,2568398500,2460823400,2467514300,2520304500,2553481900,3227795800,3210969000,2339868200,2592902200,2584805200,2606822900,2562347600,2547035700,3246748100,3882983700,3190825400,2878416200,2768595700,3341617800,2692529600,2748581300,6749438400,7534298900,2248113700,2773139700,2617790000,2626582900,2624077100,2511111200,3211206200,3271968700,2554448300,2731828000,2706612600,2744433500,2963710700,2674493300,2738718700,3350820800,2770645000,2489071600,6688494300,3277047700,2495895600,2489033000,8136142700,8053662100,2468293600,2498487000,2526103200,2517918600,2592409400,2573006400,3416870000,3213595200,2241726800,2506368600,2607313200,2006996100,2104712300,2753961100,3782967200,3849813500,2751249500,2523952200,2746044200,3298798700,2938891500,2856473700],"actions_per_second":0.30899623310545876,"host":{"platform":"Windows-11-10.0.26300-SP0","processor":"AMD64 Family 25 Model 33 Stepping 0, AuthenticAMD","python":"3.12.10"},"maximum_observation_chars":1149,"measured":true,"model_memory_bytes":null,"scope":"adapter.act wall time; includes parsing; excludes world simulation and model loading","token_throughput":null,"total_action_seconds":233.0125493}`.

Humour, surprise and distinctiveness human ratings remain null. Training loss and parity are not quality scores.

Local binaries/checkpoints are hash-indexed but are not included in this portable package or published externally:
- `artifacts/ttt-013-execution/joint/adapter/adapter_model.safetensors`
- `artifacts/ttt-013-execution/joint/adapter/tokenizer.json`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/adapter_config.json`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/adapter_model.safetensors`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/optimizer.pt`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/README.md`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/rng_state.pth`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/scaler.pt`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/scheduler.pt`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/trainer_state.json`
- `artifacts/ttt-013-execution/joint/checkpoints/checkpoint-23/training_args.bin`
- `artifacts/ttt-013-execution/joint/checkpoints/trainer_state.json`

The base model remains subject to LFM Open License v1.0. Project corpus redistribution permission is ungranted pending owner review; see data-card.md.

Limitations: small template-driven corpus; scripted T3 source policy; fixed relay private goal despite observed changing priority; conservative lexical secret detector; no CyberSand integration.
Import provenance: initial workers used the live checkout while the unrelated optional LangGraph backend received typing/lazy-import changes. A source audit preserves those changes; no full-tree-clean claim is made. Later workers use the packaged source11e archive with verified campaign import path. See the report and source audit.
