# Abstract World Authority

## Purpose

TTT's first operational environment is a small deterministic abstract world for
training and evaluating high-level commander behaviour. It is intentionally not
a physics simulator and makes no claim of CyberSand/Rapier fidelity.

The implementation lives under
`techrotic_training_triumvirate.world`.

## Framework boundary

The authoritative implementation is ordinary Python and has no dependency on
LangGraph or Concordia.

```text
typed TTT command
      |
CommandInterpreter
      |
WorldAuthority.dispatch()   <- admission/order-state mutation
      |
WorldAuthority.step()       <- later operational outcome
      |
canonical AuthoritativeEvent records
```

LangGraph may orchestrate this API later. Concordia may host it optionally.
Neither framework owns semantic world truth.

## Scenario generation

`ScenarioGenerator` is seeded and versioned as `abstract-world-v1`.

A blueprint contains:

- zones;
- routes/topology;
- generic unit archetypes;
- initial units and resources;
- objectives;
- private world facts;
- initial tick/generation;
- commander route knowledge.

The initial archetypes are generic rather than CyberSand-specific:

- scout;
- heavy;
- support;
- skirmisher.

Every generator input is explicit. Same version + config + seed produces the
same blueprint.

`ScenarioConfig(mid_state=True)` creates a coherent non-clean start with an
advanced tick/generation and an already displaced/holding unit.

## Admission versus outcome

TTT-003 command admission and world execution are separate.

An `assign_objective` command may be accepted and create a pending order even
when the chosen route is secretly blocked. The later `step()` then emits
`execution-failed`.

The abstract world currently models delayed failures including:

- `ROUTE_BLOCKED`;
- `STALL_NO_PROGRESS`;
- `RESOURCE_EXHAUSTED` after admission;
- `UNIT_LOST` on deterministic hazardous routes;
- `TARGET_STATE_CHANGED` when another order changes the objective first.

Successful travel produces progress and completion events.

This separation provides the recovery states needed by TTT-010 rather than
turning every world difficulty into an immediate parser/interpreter rejection.

## Visibility surfaces

`private_snapshot()` contains full authoritative state including:

- actual route blockage/hazards;
- resources;
- pending orders;
- private facts.

`commander_observation()` contains the commander's admitted operational view,
including visible unit energy and only routes it has discovered.

`player_observation()` is narrower: public unit/objective status without
commander-only energy/route/private state.

A blocked route hidden at scenario start becomes commander-visible only after an
actual failed attempt discovers it.

## Deterministic replay

`run_envelopes()` creates a fresh World Authority from a blueprint and replays
an exact canonical `CommandEnvelope` sequence.

Reference results carry:

- interpreter results;
- authoritative event sequence;
- final private-state hash;
- event-sequence hash;
- final commander-observation hash;
- final player-observation hash.

The model-free `run_scripted_episode()` defaults to 24 turns and intentionally
contains both delayed execution failure and an immediate post-state-change
rejection.

CLI:

```bash
ttt world-demo --seed 24301 --turns 24
ttt world-demo --seed 24301 --turns 24 --mid-state
```

## Optional Concordia host

Concordia remains optional:

```bash
python -m pip install -e ".[dev,concordia]"
```

The root optional group pins `gdm-concordia==2.4.0`, matching SPIKE-CD-001.

`run_concordia_envelopes()` uses Concordia's real `Sequential` engine but a
deterministic duck-typed Game Master. The Game Master:

- exposes TTT commander/player projections as Concordia observations;
- transports canonical TTT command envelopes as strings;
- deserializes them back into strict TTT records before interpretation;
- invokes the same `CommandInterpreter`, `WorldAuthority.dispatch()`, and
  `WorldAuthority.step()`;
- contains no language model or alternate resolution logic.

The dedicated `World Concordia parity` workflow installs the optional
dependency and requires direct/native and Concordia-hosted runs to produce the
same TTT event/final-state/visibility hashes.

## Dependency and performance policy

The direct path adds **zero third-party runtime dependencies** and remains the
path used by base CI and high-volume future corpus generation.

Concordia brings its broader scientific/simulation dependency stack, so it is
kept behind an optional group and a separate parity workflow. It should be
retained only while its richer entity/scene/Game-Master functionality provides
value that justifies that additional footprint.

The programme should revisit this tradeoff after the later 20+ turn evaluation
harness measures real workloads.
