> **Status: RESOLVED / historical handover.**
>
> Wave 3 completed on 24 October 2026. The blockers recorded below were fixed and
> must not be treated as current work instructions.
>
> - TTT-004 / #5 merged through PR #27 as
>   `ffdffb4d0f877a1fc04ad308d15d66dbef6f0cdd`.
>   Final Base CI and World Concordia parity were green.
> - TTT-008 / #9 merged through PR #26 as
>   `a70eb28a39527aeb40b69a2e9543eb54a9212b69`.
>   Its branch was reconciled onto the merged TTT-004 head and final Base CI was green.
> - The intercept forbidden-value question was resolved in favor of the documented
>   visibility-surface contract: forbidden-value refusal applies to fields actually
>   admitted to the player-visible intercept surface.
> - Current programme status and next work are authoritative in
>   `docs/rag/09-implementation-programme.md`.
>
> The remainder of this file is retained only as a record of the mid-Wave-3 state.

# 2026-10-24 Wave 3 implementation handover

## Repository state

Current `main`: `3c3f56f04aa6334ad43e252434f31182adc415c8`.

Completed and merged in this implementation session:

- TTT-001 / #2 — repository/package bootstrap.
- TTT-002 / #3 — canonical versioned schemas and T0 fixtures.
- TTT-003 / #4 — `ttt-command-v1`, strict command parser/interpreter and stable rejection taxonomy. Merge: `d4b163ff8b73ec5f9ee913022a4ae0807390ffa2`.
- TTT-006 / #7 — model-agnostic Creative Teacher/persona subsystem. Merge: `3c3f56f04aa6334ad43e252434f31182adc415c8`.

Architecture decisions remain:

- LangGraph: adopted orchestration/checkpoint/branch/replay substrate.
- Concordia: optional richer simulation/Game-Master host only; TTT canonical semantics remain framework-neutral.

## TTT-004 / #5 — World Authority

Working branch: `feat/ttt-004-world-authority`.

Working PR: #27 — **TTT-004: implement deterministic World Authority with optional Concordia host**.

Recorded implementation head before this handover:
`08465580555be3f2d13ddd33a9e436f5fbaa54ed`.

Implemented on the branch:

- seeded/versioned abstract scenario generator;
- zones/routes and generic unit archetypes;
- clean and mid-state scenario starts;
- TTT-003 `WorldAdapter` implementation;
- pending accepted orders separated from later `step()` outcomes;
- deterministic delayed failures including route blocked, stall/no-progress, resource exhaustion, unit loss and target-state change;
- private / commander / player projections;
- canonical state/event/visibility hashes;
- native replay/driver and 24-turn reference episode;
- `ttt world-demo`;
- optional `gdm-concordia==2.4.0` host;
- dedicated `World Concordia parity` workflow.

Latest CI:

- Python 3.12 tests: **PASS**.
- Python 3.13 tests: **PASS**.
- World Concordia parity: **PASS**.
- Base CI static-quality job: **FAIL at Ruff lint only**; format/mypy were not reached.

Current Ruff blockers:

1. `src/techrotic_training_triumvirate/world/__init__.py`
   - import ordering;
   - one 90-character `driver` import line.
2. `src/techrotic_training_triumvirate/world/scenario.py`
   - import ordering;
   - B008: `ScenarioConfig()` used directly as a function default. Change to `None` + construct inside, or a module-level immutable singleton.

Recommended resume sequence:

1. Fix those four Ruff findings without changing semantics.
2. Run Base CI again and address formatter/mypy findings if exposed.
3. Reconcile #27 against current `main` if any other PR merges first.
4. Confirm parity workflow remains green on the exact final head.
5. Merge #27 and verify #5 closes.

## TTT-008 / #9 — player intercept codec

Working branch: `feat/ttt-008-player-intercepts`.

Working PR: #26 — **TTT-008: implement grounded player intercept and deception codec**.

Current PR head:
`859832aeecbf0cca5a7fd328eef74ca43d450448`.

Implemented:

- ordinary intercepts grounded only in canonical `command-dispatched` events;
- bounded intercept semantic field surface;
- versioned doctrine/codeword aliases;
- deterministic redaction, alias substitution, field dropping, corruption and delay;
- grounding back to source event IDs;
- explicit authoritative `deception-broadcast` event path;
- normal and deceptive `PlayerInterceptEnvelope` generation;
- hidden-value guard and grounding tests.

Latest CI:

- Base CI tests fail on both Python versions with **1 failing intercept test**.
- Static-quality job also has Ruff findings.

Functional failure:

`test_private_or_forbidden_values_cannot_escape_ordinary_intercept` expects
`InterceptVisibilityError` when a forbidden value is put in the dispatch
`channel` field. The default `InterceptPolicy.reveal_fields` does not include
`channel`, so the forbidden value is dropped before the forbidden-value scan and
no exception is raised.

This needs a deliberate policy decision, not a blind test edit:

- **Option A:** forbidden-value protection applies only to values that would
  actually become player-visible. Then change the test to use a revealed field
  or explicitly include `channel` in `reveal_fields`.
- **Option B:** forbidden-value protection is a stronger source-side invariant.
  Then scan eligible source semantics for forbidden values before reveal/drop.
  
The existing design text says the guard protects emitted player-visible
semantics, so **Option A is the current contract-consistent interpretation**.

Current Ruff blockers include:

- import ordering in `intercepts/model.py` and `intercepts/policy.py`;
- line wrapping in `DoctrineLexicon.__post_init__`;
- remove quoted forward annotation on `SemanticIntercept`;
- wrap the long `deception_event` docstring;
- combine nested drop-probability `if` statements (SIM102).

Recommended resume sequence:

1. Resolve the forbidden-value test according to the intended visibility contract.
2. Apply the Ruff fixes above.
3. Run Base CI through Ruff format and strict mypy.
4. Reconcile onto current main after TTT-004 if #27 merges first.
5. Merge #26 and verify #9 closes.

## Programme position

Wave 2 is complete.

Wave 3 is active:

- TTT-004 / #5: implemented, functional tests + Concordia parity green; static-quality cleanup pending.
- TTT-008 / #9: implemented, one visibility-policy test decision + static-quality cleanup pending.

Do **not** start model selection or model downloads. TTT-011 remains the explicit model-cast gate.

## Resume principle

Continue from the existing PR heads. Do not recreate TTT-004 or TTT-008 from the issue prompts. Preserve:

- admission vs execution-success separation;
- framework-neutral native World Authority as canonical path;
- Concordia as optional transport/simulation host only;
- ordinary intercept grounding in real dispatch events;
- explicit deception events for false tactical broadcasts;
- no model-selection changes before TTT-011.
