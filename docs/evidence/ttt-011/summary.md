# TTT-011 live model-probe summary

Source commit: `0a16e3c5138d4ea724a37747da8b8fec18278b8a`

| Model | Structured | Secret | Recovery | TTFT s | tok/s | Peak RSS MiB |
|---|---:|---:|---:|---:|---:|---:|
| lfm2.5-1.2b-instruct | PASS | PASS | FAIL | 0.160 | 27.40 | 1259.8 |
| qwen3.5-4b | PASS | PASS | PASS | 1.124 | 4.35 | 4707.6 |
| sprocket-500m | FAIL | PASS | FAIL | 0.087 | 68.85 | 612.2 |

Behavioral failures are evidence, not workflow failures. Artifact/hash/runtime failures fail closed.

See the sibling `*-probe.json` records for complete prompts, decoding settings, outputs, hardware/runtime metadata and diversity samples.
