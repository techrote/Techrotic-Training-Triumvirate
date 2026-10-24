# Deterministic baseline evidence

These are reference controls generated from unchanged evaluation and authority
sources at commit `11e70686b09a27cf7c784beaf8d7a46717b345a0`.

- `benchmark.json` and `benchmark.md`: the complete original TTT-009 frozen
  benchmark using `ScriptedCommanderBaseline`.
- `closed-loop.json` and `closed-loop.md`: complete TTT-014 24-turn evidence
  using `ClosedLoopBaseline`, including every action, result, event and intercept.
- `evidence-manifest.json`: source commit, per-imported-module source/blob hashes,
  protocol/report identities and repeat/replay verification results.
- `SHA256SUMS`: exact stored file hashes, including this readme and generator.

No model, GPU, paid service, network call or external download is used. Runtime
measurement is disabled, so these reports make no performance claim. Scripted
controls explicitly carry `substantive=false` and `quality_evidence=false`.
They cannot substitute for real model quality evidence or runtime admission.

The original benchmark and extended closed-loop suite use different baseline
policies appropriate to their respective contracts. Their results should not be
mistaken for one policy evaluated under two identical environments.

Regeneration requires a separate checkout of historical source
`11e70686b09a27cf7c784beaf8d7a46717b345a0`. Copy this baseline directory into
that checkout, point `PYTHONPATH` at its `src` directory, and run
`python docs/evidence/ttt-014/baseline/reproduce.py` there. Later `main` versions
include source changes such as optional LangGraph handling, so the generator
deliberately refuses regeneration from current `main` even when those changes
preserve the evaluation's semantics.

The generator refuses if any imported TTT source or frozen benchmark definition
differs from the recorded commit. Windows checkout newline conversion is
normalized for source comparison; actual executed file SHA-256 hashes are also
retained. Both baselines are repeated and closed-loop actions are authoritatively
replayed before reports are written.

Current `main` can independently replay the stored closed-loop evidence without
the original model, training dependencies or historical checkout:

```bash
ttt closed-loop-verify --report docs/evidence/ttt-014/baseline/closed-loop.json
```
