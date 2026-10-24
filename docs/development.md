# Development

The base TTT package is intentionally lightweight and model-agnostic.

## Supported Python

The core package supports Python **3.12 and 3.13**. Base CI exercises both versions. Optional ML or simulation integrations may later document narrower interpreter requirements without narrowing the core unnecessarily.

## Install

From the repository root:

```bash
python -m pip install -e ".[dev]"
```

The base runtime has no third-party dependencies. Developer tools live in the `dev` optional dependency group. Future heavyweight model/training/provider dependencies must also live in explicit optional groups rather than the base install.

The architecture spikes under `spikes/` remain isolated packages with their own dependency pins and workflows.

The implemented World Authority has a dependency-free native path. To run the optional Concordia parity host:

```bash
python -m pip install -e ".[dev,concordia]"
python -m pytest tests/test_world_concordia.py
```

The optional group pins `gdm-concordia==2.4.0`, matching the admitted architecture spike.

TTT-005 keeps LangGraph optional so the native World Authority remains dependency-free.
Install and exercise the session/checkpoint integration with:

```bash
python -m pip install -e ".[dev,session]"
python -m pytest tests/test_session_rendering.py tests/test_session_langgraph.py tests/test_recovery.py tests/test_recovery_langgraph.py
```

The `session` extra pins `langgraph==1.2.17`, matching SPIKE-LG-001. TTT-010's LangGraph-backed corrective runner also lives behind this optional extra; the recovery adapter/model/oracle contracts remain importable in the dependency-free base package.

## Canonical checks

Run each check from the repository root:

```bash
python -m pytest
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src
```

These are the same base checks enforced by `.github/workflows/base-ci.yml`.

## CLI smoke checks

```bash
ttt --version
ttt seed-demo --seed 24301 --count 5
ttt schema-bundle --pretty
ttt command-schema --pretty
ttt world-demo --seed 24301 --turns 24
```

The seed demo exists to make deterministic plumbing observable without requiring a simulator or model. The schema-bundle command emits the canonical durable-record JSON Schema bundle. The command-schema command emits the independently versioned TTT command-body contract. The world-demo command runs the model-free deterministic reference episode and emits state/event hashes.

## Reproducibility rule

Randomized implementation and tests must accept an explicit seed and should use an isolated RNG rather than mutating process-global random state. `techrotic_training_triumvirate.determinism.seeded_rng` is the initial helper.

The smoke suite records the exact five-value sequence for seed `0x5EED` and verifies it on every supported Python version. A change to that recorded sequence is therefore an explicit compatibility event, not a silent test drift.

## Artifact hygiene

The root `.gitignore` excludes common model weights/checkpoints and generated experiment/corpus directories. Small intentional fixtures may be force-added when an issue explicitly requires them, but large generated evidence belongs in an external/artifact store with hashes and manifests committed to git.
