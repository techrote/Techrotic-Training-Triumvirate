# LangGraph checkpoint → branch → correction → replay spike

Issue: #18  
Scope: architecture spike only; does not implement TTT-003, TTT-004, or TTT-005.

## Question

Can LangGraph provide TTT's generic workflow checkpoint/branch/replay machinery while a separate deterministic World Authority continues to own semantic truth?

## Tested dependency

- Python 3.12 in CI
- `langgraph==1.2.17`
- `InMemorySaver` for the contained proof

The spike deliberately uses no LLM, model API, network service, database, or game engine.

## Tiny deterministic world

The world contains:

- staging location;
- one relay objective;
- a blocked `direct` route;
- a valid `flank` route;
- one private world fact excluded from the commander observation.

The original command is:

```json
{"op":"move","target":"relay","route":"direct"}
```

The World Authority rejects it with `ROUTE_BLOCKED` and leaves authoritative world state unchanged.

The correction is:

```json
{"op":"move","target":"relay","route":"flank"}
```

It succeeds and secures the relay.

## Proof sequence

```
START
  |
observe
  |       <-- persisted checkpoint immediately before command application
  v
apply_command(direct)
  |
  +--> ROUTE_BLOCKED ---------------------------- original failed final checkpoint
  |
  +-- historical checkpoint update: command=flank
            |
            +--> distinct branch checkpoint
                    |
                    v
              apply_command(flank)
                    |
                    +--> RELAY_SECURED ----------- corrected result
                    |
                    +-- replay same branch checkpoint
                              |
                              +--> RELAY_SECURED -- identical semantic hash
```

The automated test also addresses the original failed final checkpoint after the corrected branch/replay and verifies its semantic hash is unchanged.

## What LangGraph owns in the spike

- execution order;
- thread identity;
- checkpoint persistence;
- historical checkpoint lookup;
- branch creation via `update_state`;
- replay from a specific checkpoint.

## What TTT still owns

- command meaning;
- command acceptance/rejection;
- authoritative world state;
- visibility/private-state projection;
- events and error semantics;
- canonical semantic hashing;
- experimental provenance.

LangGraph checkpoint IDs and metadata are orchestration evidence, **not** replacements for TTT's future canonical episode/event/provenance records.

## Acceptance evidence

Automated tests assert:

1. the blocked command fails without world mutation;
2. private state is excluded from commander observation;
3. a checkpoint before `apply_command` is discoverable;
4. historical `update_state` creates a distinct checkpoint containing the corrected command;
5. the corrected branch succeeds;
6. invoking from that branch checkpoint again reproduces the same TTT semantic hash;
7. the original failed final checkpoint remains independently readable;
8. separate threads produce identical semantic hashes despite different LangGraph checkpoint IDs.

Run locally:

```bash
python -m pip install -e "./spikes/langgraph[test]"
python -m pytest spikes/langgraph/tests
python -m ttt_langgraph_spike
```

## Architecture decision

**Decision: ADOPT LangGraph for TTT orchestration/checkpoint/branch/replay substrate.**

The contained proof passed unchanged in GitHub Actions on PR #19. Use LangGraph as the preferred orchestration/checkpoint/branch substrate for later TTT session and corrective-rollout work, while retaining TTT-owned semantic state, event records, hidden-information policy, hashes, and provenance.

Do **not** make LangGraph a dependency of the deterministic World Authority itself. The World Authority should remain callable as ordinary deterministic code and testable without LangGraph so the project can replace the orchestration layer later if necessary.

This decision should be revisited if later persistence backends, scale, or exact replay requirements reveal semantics that cannot be represented without leaking LangGraph-specific details into canonical TTT contracts.
