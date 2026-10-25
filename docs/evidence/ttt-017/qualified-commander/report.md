# Commander continuation qualification

Outcome: **ADMITTED**, subject to the scope and limitations below.

Semantic source: `f152cafc59bda5207b8cb1c5ef7d6d60133d1b41`. Reporter source: `ba904aad3c6640b524960f5c2a61dd8b4bc330d9`.

The initial TTT-016 negative study and failed continuation attempts remain historical evidence. Attempt-03 was rejected on fresh development without a frozen readout. This result applies to the exact trained Q4 candidate bound here.

## Operational and automated character results

```json
{
  "mechanical": 0.9974358974358974,
  "rejection_recovery": 1.0,
  "frozen_commands": 77,
  "long_objectives": 1.0,
  "long_recovery": 1.0,
  "long_schema": 1.0,
  "long_repetition": 0.0,
  "long_character": {
    "constraint_adherence_rate": 1.0,
    "doctrine_consistency_rate": 1.0,
    "lexical_diversity": 0.19931961706155255,
    "phrase_diversity": 0.3107043316215565,
    "repetition_rate": 0.0
  },
  "frozen_critical": 0,
  "frozen_hidden_fact_use": 0,
  "long_critical": 0,
  "passed": true
}
```

## Measured Q4 runtime

```json
{
  "artifact_sha256": "2036e8c9a17038c0e503ae1af16a567673e59f37337f1cf09b40c2b2fdb819e0",
  "artifact_size_bytes": 730894720,
  "candidate_id": "commander-repair-v2",
  "context_tokens": 2048,
  "decode_tokens_per_second": 290.00151797669565,
  "host": "{\"gpu\":{\"actual_cuda_name\":\"NVIDIA TITAN RTX\",\"actual_cuda_uuid\":\"GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8\",\"driver_index\":null,\"identity_verified\":true,\"name\":null,\"pci_bus_id\":null,\"uuid\":\"GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8\",\"visible_cuda_ordinal\":0},\"memory_measurement\":\"server working-set RSS sampled every 20ms; GPU allocations separately logged\",\"platform\":\"Windows-11-10.0.26300-SP0\",\"runtime_environment\":{\"GGML_CUDA_DISABLE_GRAPHS\":\"1\"},\"server_sha256\":\"a41e1f09439d7ccdd5f43acd53aa410eedadf17961765fb11a145242759a8167\",\"settings\":[\"C:\\\\cybernpc2\\\\Techrotic-Training-Triumvirate\\\\artifacts\\\\ttt-017\\\\tools\\\\llama-win\\\\llama-server.exe\",\"--model\",\"C:\\\\cybernpc2\\\\Techrotic-Training-Triumvirate\\\\artifacts\\\\ttt-017\\\\export-04\\\\commander-Q4_K_M.gguf\",\"--alias\",\"ttt-commander-2036e8c9a17038c0\",\"--ctx-size\",\"2048\",\"--parallel\",\"1\",\"--jinja\",\"--threads\",\"8\",\"--batch-size\",\"512\",\"--ubatch-size\",\"128\",\"--n-gpu-layers\",\"99\",\"--host\",\"127.0.0.1\",\"--port\",\"18087\"]}",
  "model_role": "primary",
  "peak_resident_memory_bytes": 1351196672,
  "quantization": "Q4_K_M",
  "schema": "ttt.runtime_measurements",
  "schema_version": 1,
  "ttft_seconds": 0.054307300015352666
}
```

## Supplied human ratings

```json
{
  "schema": "ttt.human_ratings",
  "schema_version": 1,
  "candidate_id": "commander-repair-v2",
  "ratings": [
    {
      "reviewer_id": "owner-chat-2026-10-25",
      "humour": 2,
      "surprise": 2,
      "distinctiveness": 3
    }
  ]
}
```

Scores are supplied review data. Template adherence and loss do not substitute for them; their presence does not establish broad subjective quality.

## Compute accounting

Continuation charge: 2.759292 GPU-equivalent hours against a 22-hour cap, including failures and runtime qualification. Initial-study consumption is separately preserved (0.962306 hours). Only the admitted TITAN RTX is selected; no V100, paid API or external compute is authorized by this package.

## Limitations

- One selected continuation candidate and scripted control; not a new four-way ablation.
- Synthetic English abstract worlds; no downstream game integration claim.
- Scripted oracle/templates; no model-generated teacher or learner-visited training contribution.
- Episode/seed splits are disjoint; generator families and style vocabulary overlap.
- Codec, observation coverage, data volume and SFT exposure are confounded.
- Automated secrecy and character detectors have limits; human review has a small sample.
- Weights remain local and unpublished. A clean clone must restore every hash-bound binary before full readback.
- Corpus redistribution remains ungranted pending owner licence review; native LFM licence/notices apply.
