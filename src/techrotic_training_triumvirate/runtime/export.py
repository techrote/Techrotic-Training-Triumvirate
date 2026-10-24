"""Hash-verified admission and native tiny inference for TTT-012 exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

from techrotic_training_triumvirate.evaluation.model import (
    EvaluationContext,
    PolicyIdentity,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    JsonObject,
    canonical_json,
    content_hash,
)
from techrotic_training_triumvirate.schemas.base import (
    require_exact_keys,
    require_json_object,
    require_str,
)
from techrotic_training_triumvirate.training import (
    TrainingMix,
    map_source_example,
    resolve_model_binding,
)
from techrotic_training_triumvirate.training.export import sha256_file
from techrotic_training_triumvirate.training.model import SourceExample

from .host import RuntimeHost
from .protocol import (
    DEFAULT_LIMITS,
    RuntimeLimits,
    RuntimeProtocolError,
    bounded_json,
    runtime_message,
    runtime_record,
)

_METADATA_LIMITS = RuntimeLimits(
    max_bytes=4_194_304, max_nodes=65_536, max_items=8_192, max_string_bytes=65_536
)


def runtime_source_example(
    context: EvaluationContext, action: AssistantAction
) -> SourceExample:
    """The explicit v1 prompt mapping shared by runtime and tiny training fixtures.

    Training callers must obtain ``action`` from admitted episodes/oracles. This
    helper itself neither labels nor admits model-generated targets.
    """
    return SourceExample(
        example_id=f"{context.case_id}:{context.turn_index}",
        split="train",
        tier="T1",
        mode="standard",
        input={
            "runtime_prompt_version": "ttt-runtime-prompt-v1",
            "observation": context.observation.to_dict(),
            "observation_generation": context.observation_generation,
            "persona": context.persona.to_dict(),
            "previous_results": [
                result.to_dict() for result in context.previous_results
            ],
            "recent_events": [event.to_dict() for event in context.recent_events],
        },
        target=action.to_payload(),
    )


def runtime_prompt(context: EvaluationContext) -> str:
    source = runtime_source_example(context, AssistantAction((), ()))
    # Empty targets are excluded by the training mapper; an inert valid placeholder
    # affects only the ignored target, never the prompt messages.
    source.target["communications"] = [
        {
            "schema": "ttt.communication",
            "schema_version": 1,
            "payload": {
                "communication_id": "prompt-only",
                "channel": "squad",
                "text": "",
                "recipients": [],
            },
        }
    ]
    mapped = map_source_example(source, mix=TrainingMix.JOINT_CORRECTIVE)
    if mapped is None:
        raise AssertionError("runtime prompt fixture must map")
    return canonical_json([message.to_object() for message in mapped.prompt_messages])


def _read_metadata(path: Path) -> JsonObject:
    if path.stat().st_size > _METADATA_LIMITS.max_bytes:
        raise RuntimeProtocolError("export metadata size limit exceeded")
    return require_json_object(
        bounded_json(path.read_bytes(), limits=_METADATA_LIMITS), field=path.name
    )


def _digest(value: object) -> str:
    text = require_str(value, field="sha256")
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise RuntimeProtocolError("export SHA-256 must be lowercase hexadecimal")
    return text


def _artifact_path(root: Path, name: str) -> Path:
    # Refuse both Windows and POSIX escape spellings, irrespective of host OS.
    posix, windows = PurePosixPath(name), PureWindowsPath(name)
    if (
        not name
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or ".." in windows.parts
    ):
        raise RuntimeProtocolError("export artifact path escapes its directory")
    resolved = (root / name).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise RuntimeProtocolError(
            "export artifact must be a file within its directory"
        )
    return resolved


@dataclass(frozen=True, slots=True)
class VerifiedTinyExport:
    root: Path
    manifest_sha256: str
    model_key: str
    base_model_identity: JsonObject
    memory: dict[str, str]

    def identity(self) -> JsonObject:
        return {
            "model_key": self.model_key,
            "manifest_sha256": self.manifest_sha256,
            "base_model_identity": self.base_model_identity,
        }


def load_tiny_export(
    directory: str | Path, *, expected_manifest_sha256: str | None = None
) -> VerifiedTinyExport:
    """Admit an existing tiny export; never download weights or execute export code."""
    root = Path(directory).resolve()
    try:
        manifest_path = _artifact_path(root, "export-manifest.json")
        manifest = _read_metadata(manifest_path)
        manifest_hash = sha256_file(manifest_path)
        if expected_manifest_sha256 is not None and manifest_hash != _digest(
            expected_manifest_sha256
        ):
            raise RuntimeProtocolError(
                "export manifest hash differs from caller binding"
            )
        require_exact_keys(
            manifest,
            required={
                "manifest_version",
                "model_key",
                "base_model_identity",
                "dataset_identity",
                "training_config",
                "tiny_model_hash",
                "artifact_hashes",
                "parity",
                "quantization",
            },
        )
        if (
            type(manifest["manifest_version"]) is not int
            or manifest["manifest_version"] != 1
        ):
            raise RuntimeProtocolError("unsupported training export version")
        model_key = require_str(manifest["model_key"], field="model_key")
        binding = resolve_model_binding(model_key)
        base = require_json_object(
            manifest["base_model_identity"], field="base_model_identity"
        )
        if base != binding.to_object():
            raise RuntimeProtocolError(
                "export base model does not match admitted student identity"
            )
        hashes = require_json_object(
            manifest["artifact_hashes"], field="artifact_hashes"
        )
        required = {
            "adapter.json",
            "model-binding.json",
            "parity.json",
            "run-manifest.json",
        }
        if not required <= set(hashes):
            raise RuntimeProtocolError("export manifest omits required artifacts")
        for name, digest in hashes.items():
            if sha256_file(_artifact_path(root, name)) != _digest(digest):
                raise RuntimeProtocolError(f"export artifact hash mismatch: {name}")
        if _read_metadata(root / "model-binding.json") != base:
            raise RuntimeProtocolError(
                "export model binding artifact differs from manifest"
            )
        parity = _read_metadata(root / "parity.json")
        cases = parity.get("cases")
        if (
            parity != manifest["parity"]
            or parity.get("passed") is not True
            or not isinstance(cases, list)
            or not cases
            or not all(
                isinstance(case, dict) and case.get("equal") is True for case in cases
            )
        ):
            raise RuntimeProtocolError(
                "export lacks passing save/reload parity evidence"
            )
        adapter = _read_metadata(root / "adapter.json")
        require_exact_keys(
            adapter,
            required={
                "schema_version",
                "backend",
                "training_identity",
                "model_hash",
                "memory",
            },
        )
        if (
            type(adapter["schema_version"]) is not int
            or adapter["schema_version"] != 1
            or adapter["backend"] != "tiny-deterministic-v1"
        ):
            raise RuntimeProtocolError(
                "only the native tiny export loader is available"
            )
        raw_memory = require_json_object(adapter["memory"], field="memory")
        memory: dict[str, str] = {}
        for prompt_hash, target in raw_memory.items():
            memory[_digest(prompt_hash)] = require_str(target, field="target")
        if (
            content_hash(memory) != _digest(adapter["model_hash"])
            or adapter["model_hash"] != manifest["tiny_model_hash"]
        ):
            raise RuntimeProtocolError("export memory/model hash mismatch")
        return VerifiedTinyExport(root, manifest_hash, model_key, base, memory)
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeProtocolError(str(exc)) from exc


class TinyExportStudentAdapter:
    """Concrete inference for the dependency-free TTT-012 exported memory model.

    An unseen prompt is an explicit error. It never substitutes an unreported
    scripted policy or claims to run the selected student's native weights.
    """

    def __init__(self, export: VerifiedTinyExport) -> None:
        self.export = export

    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity(
            "tiny-export", "ttt-012-tiny-runtime", self.export.manifest_sha256
        )

    def begin_case(self, *, case_id: str, seed: int) -> None:
        del case_id, seed

    def act(self, context: EvaluationContext) -> AssistantAction:
        prompt_hash = content_hash(cast(object, bounded_json(runtime_prompt(context))))
        target = self.export.memory.get(prompt_hash)
        if target is None:
            raise RuntimeProtocolError(
                "tiny export has no admitted response for this prompt"
            )
        payload = require_json_object(bounded_json(target), field="assistant target")
        action = runtime_record(
            {"schema": "ttt.assistant_action", "schema_version": 1, "payload": payload},
            expected_type=AssistantAction,
        )
        # Validate command syntax and limits even when adapter is used without a host.
        runtime_message(
            "action",
            session_id=context.case_id,
            sequence=context.turn_index + 1,
            payload={"action": action.to_dict()},
        )
        return action


def host_from_tiny_export(
    directory: str | Path,
    *,
    expected_manifest_sha256: str | None = None,
    limits: RuntimeLimits = DEFAULT_LIMITS,
) -> RuntimeHost:
    exported = load_tiny_export(
        directory, expected_manifest_sha256=expected_manifest_sha256
    )
    return RuntimeHost(
        TinyExportStudentAdapter(exported),
        model_artifact=exported.identity(),
        limits=limits,
    )
