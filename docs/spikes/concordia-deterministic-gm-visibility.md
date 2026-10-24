# Concordia deterministic Game Master + typed command + visibility spike

Issue: #20  
Scope: architecture spike only; does not implement TTT-003, TTT-004, or TTT-005.

## Question

Can Concordia's actual simulation engine host a TTT-style deterministic World Authority while preserving typed-command validation and separate world-private, commander-visible, and player-visible surfaces with **no language-model authority**?

## Tested dependency

- Python 3.12 in CI
- `gdm-concordia==2.4.0`
- Concordia release tag `v2.4.0`, commit `702998f57da71f87bf4e607abc1325ee51cca21f`
- Concordia `Sequential` engine
- Concordia `SwitchAct`

Current upstream development was also reviewed, including later deterministic Game Master examples, but the executable spike intentionally pins the latest published release rather than a moving branch.

## Fail-fast non-LLM proof

The Game Master receives an `ExplodingLanguageModel`. Any call to `sample_text` or `sample_choice` raises immediately and increments a counter.

The GM supplies explicit components for every engine path exercised:

- termination;
- observation creation;
- next acting entity;
- next action spec;
- event resolution.

Therefore `SwitchAct` never needs its LLM fallback. Successful execution with `model_calls == 0` is direct evidence that the tested GM path is deterministic/non-generative.

## Typed command boundary

The scripted Commander returns:

~~~json
{"op":"move","target":"relay","route":"flank"}
~~~

Concordia carries entity actions as strings, so the engine prefixes the acting entity and sends a putative event to the GM.

The deterministic resolution component strips only the Concordia envelope and then calls `TttCommand.from_json`.

`TttCommand` validates:

- exact fields;
- operation enum;
- admitted target;
- route enum.

Only after successful construction of the typed object may `WorldAuthority.resolve` mutate authoritative state.

This is the main integration compromise: **Concordia's entity/action interface is string-based, while TTT's semantic command layer remains typed immediately inside the GM boundary.**

## Visibility surfaces

The authoritative state contains:

~~~text
world_private
  location
  relay_secured
  blocked_routes
  private_fact = relay-backup-generator-online
  commander_objective
  public_status
~~~

The observation component projects two different views from that state:

~~~text
Commander
  location
  relay_secured
  known_blocked_routes
  objective
  public_status

Player
  relay_secured
  public_status
~~~

Tests assert that `private_fact` reaches neither observation, and that commander-only route/objective data never reaches the player surface.

## Actual Concordia execution path

~~~text
Concordia Sequential.run_loop
        |
        +--> GM TERMINATE component ----------> "No"
        |
        +--> GM MAKE_OBSERVATION
        |       +--> Commander projection
        |       +--> Player projection
        |
        +--> GM NEXT_ACTING ------------------> Commander
        |
        +--> GM NEXT_ACTION_SPEC -------------> free JSON TTT command
        |
        +--> Commander.act -------------------> JSON command string
        |
        +--> Sequential.resolve
                |
                +--> GM.observe([putative_event] ...)
                |
                +--> GM RESOLVE component
                        |
                        +--> TttCommand.from_json
                        |
                        +--> deterministic WorldAuthority.resolve
~~~

No language model participates in this path.

## Automated acceptance evidence

Tests assert:

1. Concordia's real sequential engine executes one complete action/resolution step;
2. fail-fast language model call count remains zero;
3. a JSON command becomes a typed `TttCommand` before world mutation;
4. valid flank command deterministically secures the relay;
5. malformed enum values are rejected before mutation;
6. well-typed but blocked direct route is rejected without mutation;
7. private state is distinct from commander and player views;
8. commander-only operational information stays out of player view;
9. repeated runs produce identical world and observation hashes.

Run locally:

~~~bash
python -m pip install -e "./spikes/concordia[test]"
python -m pytest spikes/concordia/tests
python -m ttt_concordia_spike
~~~

## Preliminary architecture decision

**Decision: pending green CI.**

The spike is intended to decide whether Concordia should be:

- adopted as the mandatory TTT deterministic world engine;
- conditionally adopted as an optional/richer simulation substrate under TTT contracts and LangGraph orchestration; or
- rejected if its string/action or Game Master abstractions require too much semantic bypassing.

Regardless of outcome, TTT's typed commands, visibility policy, semantic hashes, event identities, and provenance remain authoritative.
