# Attempt-04 qualification evidence

The owner resumed the paused attempt on 25 October 2026. CPU readback verified
the completed three-epoch adapter and all nine inventoried artifacts, then the
archived worker reused it without repeating optimization. The original pause
records remain immutable in the [pause proof bundle](../pause-2026-10-24/).

## Native evaluation

The [native snapshot](native/) preserves all 226 real model actions: 77 fresh
development actions, 77 frozen benchmark actions and 72 long-session actions.
The development gate passed before the frozen readout.

| Metric | Native result | Required |
|---|---:|---:|
| Frozen mechanical score | 0.9974358974 | >= 0.95 |
| Frozen rejection recovery | 1.0 | >= 0.80 |
| 24-turn objective completion | 1.0 | >= 0.80 |
| 24-turn execution-failure recovery | 1.0 | >= 0.80 |
| Long-session schema validity | 1.0 | >= 0.95 |
| Long-session repetition proxy | 0.0 | <= 0.50 |
| Frozen/long critical detections | 0 / 0 | 0 |

The full three-by-24-turn report passes authoritative replay. The default test
suite also reconstructs the frozen and long-session runs from their actual
recorded actions without loading a model. These are measured native results;
they do not qualify a different quantized artifact. Automated secrecy and
character detectors have limits.

Training run: `ttt-012-train-export-791d6d18b367582e`. Semantic source:
`f152cafc59bda5207b8cb1c5ef7d6d60133d1b41`. Dataset:
`028dfa357fd91e10e4aaa982deff583b4de0fae49e320e29df3a167de9822105`.
Adapter SHA-256:
`daa08ab3f0c1e7fd876626f44f96eb0748a8eebc0386ab7a6d1ffa949ddb6eb0`.
The native evaluation phase charged 0.1701777778 GPU-equivalent hours, bringing
the continuation total to 2.7235155556 hours before Q4 qualification.

Only TITAN RTX UUID `GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8` was used.
CPU merge/export and Q4 transport have their own source identity
`8ba6a515f6a163642f945a3786b6b44044a2f2b4`; they do not relabel training.
Large adapter/model/derivative binaries remain local under ignored `artifacts/`.

**Admission remains incomplete:** genuine supplied human review and strict
complete-package readback are still required. The
original negative study and rejected attempt-03 remain unchanged.

## First Q4 runtime attempt

The same candidate passed the frozen and full long-session behavioral gates
after Q4_K_M quantization. Its 730,894,720-byte artifact SHA-256 is
`2036e8c9a17038c0e503ae1af16a567673e59f37337f1cf09b40c2b2fdb819e0`.
However, original runtime attempt `artifacts/ttt-017/q4-04` failed TTFT:
6.972509 seconds (maximum of all three uncached streamed probes), compared with
the two-second target. Peak server RSS was 1,510,866,944 bytes and median decode
267.620623 tokens/s. That failure and its charge are retained. A separately
recorded attempt will test an explicit graph-disabled runtime configuration,
with the first request still measured and all original thresholds unchanged.

## Final measured Q4 configuration

The [graph-disabled snapshot](q4-graphs-disabled/) passed all machine gates.
The [first Q4 snapshot](q4-runtime-miss/) retains the measured runtime miss;
[export records](export/) bind both evaluations to the identical trained Q4
artifact and preserve both charges. No optimization was repeated.

| Metric | Graph-disabled Q4 | Required |
|---|---:|---:|
| Frozen mechanical score | 0.9974358974 | >= 0.95 |
| Frozen rejection recovery | 1.0 | >= 0.80 |
| 24-turn objectives / execution recovery | 1.0 / 1.0 | >= 0.80 each |
| Long-session schema / repetition | 1.0 / 0.0 | >= 0.95 / <= 0.50 |
| Frozen / long critical detections | 0 / 0 | 0 |
| Usable context | 2,048 tokens | >= 2,048 |
| Artifact size | 730,894,720 bytes | <= 1,000,000,000 |
| Peak server working-set RSS | 1,351,196,672 bytes | <= 3,000,000,000 |
| Maximum streamed TTFT, three uncached probes | 0.0543073 seconds | <= 2 |
| Median decode, three probes | 290.001518 tokens/s | >= 12 |

The runtime setting is explicitly `GGML_CUDA_DISABLE_GRAPHS=1`; transport source
is `ba904aad3c6640b524960f5c2a61dd8b4bc330d9`, separate from the original export
driver and unchanged training/evaluation semantics. All first-request samples
remain included. The speed difference does not independently establish a causal
effect of graph capture: process/driver caches and startup state may differ.
The first configuration's frozen and long-session readout preceded the second,
so this repeated evaluation of the same adapter/Q4 bytes is disclosed; only a
runtime setting changed, and no frozen action was copied into training.

The native and both Q4 traces replay from actual recorded model actions in
default CI. Complete snapshots bind their small files through `SHA256SUMS`;
large weights remain local. The graph-disabled attempt charged 0.0139061111
GPU-equivalent hours after the first Q4 attempt's 0.0218708333 hours. Total
continuation charge is **2.7592925 of 22 hours**, with no reservations remaining.

A blinded A/B packet was prepared and supplied to the owner for genuine integer
1-5 humour, surprise and distinctiveness scores on 25 October. Its identity key
is kept separate during review. Until those scores are supplied and the strict
package verifies against actual local binaries, no ADMITTED outcome is claimed.

PR #42 was merged on 24 October while this chat was paused; today's evidence
and runtime fix use a follow-up branch. The deterministic controller core and
non-GPU hardening also landed independently in PRs #44/#46 during the pause.
This run uses its previously recorded one-experiment helper and does not claim
to validate the new controller's GPU integration.
