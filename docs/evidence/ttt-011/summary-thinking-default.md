# TTT-011 live model-probe summary

Source commit: `be9a20e8e211fb30944a493b97cc3ef5557983e5`

| Model | Structured | Secret | Recovery | TTFT s | tok/s | Peak RSS MiB |
|---|---:|---:|---:|---:|---:|---:|
| lfm2.5-1.2b-instruct | PASS | PASS | FAIL | 0.158 | 26.35 | 1257.9 |
| qwen3.5-4b | FAIL | PASS | FAIL | 0.000 | 5.16 | 4721.4 |
| sprocket-500m | FAIL | PASS | FAIL | 0.087 | 66.31 | 613.1 |

Behavioral failures are evidence, not workflow failures. Artifact/hash/runtime failures fail closed.

See the sibling `*-probe.json` records for complete prompts, decoding settings, outputs, hardware/runtime metadata and diversity samples.
