# Runtime bridge and game-facing protocol

TTT-015 implements `techrotic_training_triumvirate.runtime`. The model host and
game exchange strict JSON messages under `ttt-runtime-v1`; the canonical durable
record schemas and `ttt-command-v1` retain their independent version identities.
The native World Authority remains the authority for command admission and
execution. The runtime host receives no world object or dispatcher.

## Wire envelope

Every message has exactly these fields:

```json
{
  "schema": "ttt.runtime_message",
  "schema_version": 1,
  "protocol_version": "ttt-runtime-v1",
  "kind": "action",
  "session_id": "match-17",
  "request_id": "observation-1",
  "sequence": 1,
  "payload": {
    "action": {
      "schema": "ttt.assistant_action",
      "schema_version": 1,
      "payload": {"commands": [], "communications": []}
    }
  }
}
```

`parse_runtime_message` accepts a JSON object, UTF-8 JSON text/bytes, or an
in-process `RuntimeMessage`. Every endpoint reparses even in-process objects.
Unknown fields, schemas, versions and message kinds refuse; nested canonical
records pass through the canonical strict registry loader. Duplicate JSON keys,
non-finite numbers, unsupported Python objects and integers outside signed
64-bit range refuse. Input dictionaries are copied before use.

`runtime_message` constructs an envelope through the same validator. `to_json`
uses TTT canonical JSON. Transport framing and authentication remain the
responsibility of an IPC/network implementation; a wire schema cannot establish
that a remote peer is the game's authority.

| Kind | Direction | Exact payload fields |
|---|---|---|
| `health_request` | Game to host | `runtime_protocol_versions`, `command_protocol_versions` |
| `health` | Host to game | `status`, `implementation_version`, `runtime_protocol_versions`, `command_protocol_versions`, `capabilities`, `limits`, `policy`, `model_artifact` |
| `reset` | Game to host | `seed`, canonical `persona` |
| `started` | Host to game | `policy`, `model_artifact` |
| `observation` | Game to host | `observation_generation`, canonical `observation`, `previous_results`, `recent_events` |
| `action` | Host to game | canonical `action` |
| `feedback` | Game-owned notification | `observation_generation`, canonical `results`, canonical `events` |
| `dispatch` | Game-owned notification | canonical `event` of kind `command-dispatched` or `deception-broadcast` |
| `intercept` | Game-owned notification | canonical `intercept` with payload/rendering and source event IDs |

Version arrays must be nonempty and duplicate-free. The host refuses health
negotiation without a shared runtime **and** command protocol. `health` reports
the package version, StudentAdapter policy/adapter/revision and effective limits.
`model_artifact` is null for a script; an exported host reports the model key,
export manifest SHA-256 and immutable admitted base-model binding. A tiny export
is explicitly identified as `ttt-012-tiny-runtime`, not native model inference.

## Bounds and session ordering

The default `RuntimeLimits` apply equally to received requests and emitted
responses:

| Bound | Default |
|---|---:|
| Message UTF-8 bytes | 65,536 |
| JSON nesting depth | 20 |
| JSON nodes, including object keys | 4,096 |
| Entries per JSON object/array | 256 |
| UTF-8 bytes per string | 16,384 |
| Commands per action | 8 |
| Communications per action | 8 |
| Feedback events per message | 64 |
| Session/request/command identity length | 128 characters |

An explicitly configured smaller/larger positive limit is reported in health.
The caller must honor the host's reported limits; exceeding either endpoint's
limits refuses. Metadata loading for tiny exports uses a separate 4 MiB bound
and never loads a heavyweight checkpoint.

A host serves one active session. `reset` requires sequence zero, invokes
`StudentAdapter.begin_case(case_id=session_id, seed=seed)` and starts at turn zero.
Observations then use sequences 1, 2, ... and contiguous canonical turn IDs
0, 1, ...; observation generations must strictly increase. Action responses
repeat the request's session, request and sequence identity. The bridge validates
all three plus response kind before calling the game. Replayed command IDs
within the active session refuse before dispatch. A new explicit reset clears
the session's feedback, command IDs, pending intercepts and source registry.

Malformed messages raise `RuntimeProtocolError`; the host never converts them
into generated acknowledgements. After a transport error or a host response
rejected by the game, explicitly reset/reconcile the session before continuing.
There is no automatic network retry that could duplicate authority effects.

## Authority and visibility

`RuntimeHost` wraps the existing model-agnostic `StudentAdapter`. It accepts only
health, reset and observation requests and returns only health, start identity or
an action proposal. Dispatch, feedback and intercept messages sent to that
endpoint refuse. An action cannot contain interpreter results or world events;
its command envelopes must parse into the bounded typed command IR. Unknown
operations such as `shell` refuse. Communication text remains inert text.

`GameRuntimeAdapter` is a separate game-owned interface with reset, admitted
observation, generation/tick and action execution methods. `NativeGameAdapter`
implements it with the canonical `WorldAuthority` and `CommandInterpreter`.
The interpreter validates every command and returns exact `InterpreterResult`
records. All commands in an action use the current generation, are processed in
order, and then the native authority advances one tick. Empty/rejected actions
also advance a tick so execution feedback can continue. Accepted dispatch and
later world execution failure can occur in the same response, and remain
distinct authoritative records.

The reference bridge projects known native event kinds and a bounded whitelist
of result/event fields before sending feedback to the model. Unknown debug or
private event fields stay server-side. The commander receives only the explicit
`CommanderObservation`, persona and projected results/events. Private world
snapshots, evaluation annotations and player intercepts are never host inputs.
Downstream game adapters are responsible for correct admitted observations and
for extending projections deliberately when adding game-specific feedback.

## Grounded player intercepts

`ReferenceRuntimeBridge` obtains events only from `GameRuntimeAdapter.execute`.
For each dispatch/deception event it uses the existing `InterceptEncoder` and
checks source membership against its game-owned event registry. Ordinary
intercepts require exactly one real dispatch; deceptive intercepts require both
the explicit deception broadcast and its real dispatch, matching command IDs
and nondecreasing ticks. Duplicate event identities refuse. No model-authored
event or free-standing communication can enter this encoder path.

The `intercept` notification contains only the canonical intercept, including
the existing policy-governed semantic/rendered payload and source IDs. Full
dispatch source records are deliberately absent from this player-facing message
because they could defeat the codec's redaction. The game retains authoritative
dispatch records separately for traceability. `validate_intercept_sources` can
independently verify linkage against those authoritative records.

Delayed intercepts remain queued until the game's current tick reaches the
codec's `available_tick`. Delivery preserves the source event IDs and original
message sequence; it never claims a new command was dispatched at delivery.

## Native reference and export path

The deterministic scripted demonstration serializes every request and response
through `InProcessTransport`; it does not bypass the wire validators:

```python
from techrotic_training_triumvirate.runtime import run_runtime_demo

report = run_runtime_demo(seed=24301, turns=8)
```

`ttt runtime-demo --seed 24301 --turns 8` exposes the same reference path. The
report includes policy identity, canonical observation/action/feedback/dispatch/
intercept trace, trace hash, final World Authority hash and event hash. Default
tests use no network, model downloads, paid APIs or GPU.

`host_from_tiny_export(directory, expected_manifest_sha256=...)` is a concrete
reload/inference path for TTT-012's dependency-free `export_tiny` output. It:

1. parses bounded export metadata and rejects unsupported manifest formats;
2. verifies every declared artifact SHA-256, required files, and containment
   under the explicit export directory, including Windows/POSIX traversal and
   symlink escapes;
3. compares the base model identity to the current admitted student binding;
4. requires passing, nonempty save/reload parity evidence matching the manifest;
5. verifies the tiny memory/model hash and loads its inert JSON memory;
6. parses each selected target into a canonical bounded action before emission.

`runtime_source_example(context, action)` and `runtime_prompt(context)` define
the explicit `ttt-runtime-prompt-v1` mapping through TTT-012's existing chat
mapping. The caller must supply admitted labels and ordinary corpus provenance;
these helpers do not admit or label data. The tiny model is exact-match: an
unseen runtime prompt raises an explicit error. It never silently switches to a
script. Tests train/export a single admitted deterministic runtime fixture and
reload it into the complete bridge.

Existing general training smoke fixtures have a different prompt shape and are
not runtime-trained commander models. No native/GGUF trained model artifact is
bundled or downloaded by this issue. A future local native or GGUF
`StudentAdapter` can use the same `RuntimeHost`; its loader must verify the
selected/exported artifact and report its binding. TTT-012's HF training result
is not silently interpreted as a tiny export, and this issue makes no claim of
production native-model inference or cross-host performance admission.

## Downstream CyberSand mapping

A CyberSand integration should implement `GameRuntimeAdapter` in a separate
adapter package without changing this repository's world semantics or model
host. Stable game actor IDs become TTT entity IDs. A game snapshot/version
becomes `observation_generation`; a visibility-filtered snapshot becomes
`CommanderObservation`. Capability/resource/order checks belong to the game
authority before dispatch. Map admitted `assign_objective` to a game actor's
high-level objective API, `hold`/`cancel`/`recall` to explicit order-control APIs,
and `coordinate` to the game's bounded scheduling/objective mechanism.

The game engine continues to own movement, navigation, combat and physics.
Model text must never become a console command, shell invocation, callback,
asset path or physics script. Emit authoritative dispatch receipts after actual
admission, then emit separate completion/failure events from game execution.
Retain event IDs for intercept grounding and allow the existing codec to select
the player-visible subset. Publish only the `intercept` surface to players;
game-authority dispatch/feedback records may contain facts beyond that subset.
No CyberSand repository files are changed by TTT-015.

## Verification

```bash
python -m pytest tests/test_runtime_protocol.py tests/test_runtime_bridge.py tests/test_runtime_export.py
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src
```

Tests cover strict version/type/field refusal, duplicate JSON keys, malformed and
oversized input, nested limits, no shell operation, response correlation and
replay, authoritative rejection/execution failure, hidden-field projection,
grounded ordinary/deception/delayed intercepts, reset reproducibility and actual
hash-verified tiny export inference.
