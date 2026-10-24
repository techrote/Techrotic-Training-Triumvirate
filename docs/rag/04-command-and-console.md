# Command and console protocol

## Contents

1. Protocol identity — independent command versioning.
2. Command envelope — durable boundary between model output and IR.
3. Operation family — bounded high-level command vocabulary.
4. Parsing and validation — strict structured-input rules.
5. Interpreter admission pipeline — deterministic checks and mutation boundary.
6. Error taxonomy — stable machine-readable rejection codes.
7. Acceptance versus execution — dispatch is not success.
8. World-adapter contract — framework-neutral integration surface.
9. Execution boundary — model commands remain inert structured data.
10. Recovery and console use — how rejection data feeds later training.

## 1. Protocol identity

The first command protocol is `ttt-command-v1`. It is versioned independently
from canonical episode schemas.

## 2. Command envelope

Canonical episodes store commands in `ttt.command_envelope`:

```json
{
  "schema": "ttt.command_envelope",
  "schema_version": 1,
  "payload": {
    "command_id": "cmd-17",
    "protocol_version": "ttt-command-v1",
    "body": {
      "op": "hold",
      "observation_generation": 42,
      "unit_id": "squad-a"
    }
  }
}
```

The envelope owns durable identity/versioning. The command package parses the
body into an immutable typed command before interpretation.

## 3. Operation family

| Operation | Main fields | Purpose |
|---|---|---|
| `inspect` | entity, requested fields | Query a known entity |
| `assign_objective` | unit, objective kind, target, approach, constraints | Assign high-level intent |
| `set_constraints` | unit, constraint object | Modify execution constraints |
| `coordinate` | units, trigger, optional objective | Synchronize several units |
| `hold` | unit | Stop progression while retaining control |
| `cancel` | unit, optional order ID | Cancel an active/pending order |
| `recall` | unit, optional destination | Return/reposition a unit |
| `transmit` | recipients, channel, message | Send bounded in-world communication |
| `request_status` | entity IDs | Request current status |

Every operation carries `observation_generation`. Unknown operations and
operation-specific fields are rejected rather than ignored.

## 4. Parsing and validation

Model output can be supplied as a JSON-compatible object or JSON text:

```python
from techrotic_training_triumvirate.commands import parse_model_command

command = parse_model_command(
    {
        "op": "hold",
        "observation_generation": 42,
        "unit_id": "squad-a",
    },
    command_id="cmd-17",
)
```

Parsing validates exact field sets, required types, non-negative observation
generation, non-empty entity lists, duplicate-free multi-entity lists and the
protocol version.

`ttt command-schema` emits the structural JSON Schema 2020-12 contract.

## 5. Interpreter admission pipeline

`CommandInterpreter` follows one deterministic order:

1. parse protocol/body;
2. reject stale observation generation;
3. resolve referenced entities;
4. reject unavailable entities;
5. validate target references;
6. validate generic command capabilities;
7. ask the World Adapter for precondition checks;
8. ask for resource checks;
9. ask for active-order conflicts;
10. call `WorldAdapter.dispatch()` exactly once if all checks pass.

`dispatch()` is the only mutation boundary exposed by TTT-003. Rejected
commands never call it.

## 6. Error taxonomy

| Code | Meaning |
|---|---|
| `SCHEMA_INVALID` | malformed body, unknown operation, wrong/extra fields |
| `PROTOCOL_UNSUPPORTED` | command protocol version is unsupported |
| `ENTITY_UNKNOWN` | referenced entity does not exist |
| `ENTITY_UNAVAILABLE` | entity exists but cannot currently receive the command |
| `CAPABILITY_MISMATCH` | entity lacks the generic command capability |
| `TARGET_INVALID` | referenced target/destination/objective does not exist |
| `PRECONDITION_FAILED` | deterministic world precondition failed |
| `RESOURCE_EXHAUSTED` | required resource/budget is unavailable |
| `STALE_OBSERVATION` | command observation generation is stale |
| `ORDER_CONFLICT` | command conflicts with authoritative order state |

## 7. Acceptance versus execution

An accepted command yields an `InterpreterResult` with `accepted=True` plus
an authoritative `command-dispatched` event. This means only that the World
Authority admitted the intent for execution.

Later simulation may still report route failure, loss, timeout, changed target,
stall, or objective completion. Admission and eventual outcome remain separate.

## 8. World-adapter contract

The interpreter depends on a small `WorldAdapter` protocol:

- current observation generation;
- entity snapshots and generic capabilities;
- target existence;
- deterministic precondition/resource/conflict checks;
- final dispatch commit returning an event ID/tick/data.

TTT-004 supplies the framework-neutral World Authority and optional Concordia
host.

Generic capabilities used by v1 are:

- `command.assign_objective`;
- `command.set_constraints`;
- `command.coordinate`;
- `command.order_control`.

## 9. Execution boundary

TTT command operations describe game intent only. The protocol contains no
generic operating-system, program-launch, callback, file-operation or network
operation.

Unknown operation names and unknown fields are rejected as `SCHEMA_INVALID`.
Communication contents remain inert in-world text. Game-specific bridges map
admitted typed intent to explicit controller APIs.

## 10. Recovery and console use

Rejected records preserve the original envelope, parsed command when available,
stable error code, neutral structured detail and observation generation.

These records are intended for later corrective training. TTT-005 console
rendering must display authoritative interpreter results rather than generated
acknowledgements.
