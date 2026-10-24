"""Actual TTT-012 tiny export reload, hash admission, and runtime inference."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techrotic_training_triumvirate.commands import HoldCommand
from techrotic_training_triumvirate.evaluation.model import EvaluationContext
from techrotic_training_triumvirate.intercepts import (
    DoctrineLexicon,
    InterceptEncoder,
    InterceptPolicy,
)
from techrotic_training_triumvirate.runtime import (
    InProcessTransport,
    NativeGameAdapter,
    ReferenceRuntimeBridge,
    RuntimeProtocolError,
    TinyExportStudentAdapter,
    default_runtime_persona,
    host_from_tiny_export,
    load_tiny_export,
    runtime_source_example,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    InterpreterResult,
    canonical_json,
    load_record,
)
from techrotic_training_triumvirate.session import DeterministicRenderer
from techrotic_training_triumvirate.training import (
    TrainingMix,
    dataset_identity_from_examples,
    export_tiny,
    load_training_config,
    map_dataset,
    resolve_model_binding,
    train_tiny,
)


def _context() -> EvaluationContext:
    game = NativeGameAdapter()
    game.reset(seed=24301)
    observation = game.observation(turn_id=0)
    return EvaluationContext(
        case_id="export-session",
        turn_index=0,
        observation_generation=game.generation,
        observation=observation,
        structured_observation=observation.to_dict(),
        compact_observation=DeterministicRenderer().compact_observation(observation),
        previous_results=(),
        recent_events=(),
        persona=default_runtime_persona(),
    )


@pytest.fixture
def tiny_export(tmp_path: Path) -> Path:
    context = _context()
    action = AssistantAction(
        (
            HoldCommand(
                command_id="export-hold",
                observation_generation=0,
                unit_id="unit-1",
            ).to_envelope(),
        ),
        (),
    )
    source = runtime_source_example(context, action)
    sources = (source,)
    binding = resolve_model_binding("primary")
    config = load_training_config("primary", mix=TrainingMix.JOINT_CORRECTIVE)
    dataset = dataset_identity_from_examples(sources)
    mapped = map_dataset(sources, mix=config.mix)
    result = train_tiny(
        mapped,
        binding=binding,
        config=config,
        dataset=dataset,
        checkpoint_path=tmp_path / "checkpoint.json",
    )
    root = tmp_path / "export"
    export_tiny(
        result,
        mapped,
        binding=binding,
        config=config,
        dataset=dataset,
        output_dir=root,
        git_commit="test-runtime-export",
    )
    return root


def test_tiny_export_can_run_real_bridge_with_reported_artifact_identity(
    tiny_export: Path,
) -> None:
    exported = load_tiny_export(tiny_export)
    host = host_from_tiny_export(
        tiny_export, expected_manifest_sha256=exported.manifest_sha256
    )
    game = NativeGameAdapter()
    bridge = ReferenceRuntimeBridge(
        InProcessTransport(host),
        game,
        encoder=InterceptEncoder(
            doctrine=DoctrineLexicon("test", 1, {}), policy=InterceptPolicy("test")
        ),
    )
    started = bridge.start(
        session_id="export-session", seed=24301, persona=default_runtime_persona()
    )
    assert started.payload["model_artifact"] == exported.identity()
    turn = bridge.step()
    assert turn.intercepts
    results = turn.feedback.payload["results"]
    assert isinstance(results, list)
    assert load_record(results[0], expected_type=InterpreterResult).accepted
    assert game.world.units["unit-1"].status.value == "holding"
    with pytest.raises(RuntimeProtocolError, match="no admitted response"):
        bridge.step()


def test_tiny_export_preserves_exact_target_and_prompt_admission(
    tiny_export: Path,
) -> None:
    adapter = TinyExportStudentAdapter(load_tiny_export(tiny_export))
    action = adapter.act(_context())
    assert action.commands[0].command_id == "export-hold"
    assert action.commands[0].body["op"] == "hold"
    assert adapter.identity.revision == load_tiny_export(tiny_export).manifest_sha256


def test_export_refuses_tampered_artifact_and_manifest_binding(
    tiny_export: Path,
) -> None:
    with pytest.raises(RuntimeProtocolError, match="caller binding"):
        load_tiny_export(tiny_export, expected_manifest_sha256="0" * 64)
    adapter = tiny_export / "adapter.json"
    adapter.write_text(adapter.read_text() + " ", encoding="utf-8")
    with pytest.raises(RuntimeProtocolError, match="hash mismatch"):
        load_tiny_export(tiny_export)


@pytest.mark.parametrize(
    "path",
    [
        "../outside.json",
        "..\\outside.json",
        "C:\\outside.json",
        "/outside.json",
        "C:outside.json",
    ],
)
def test_export_refuses_artifact_path_escape(tiny_export: Path, path: str) -> None:
    manifest_path = tiny_export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifact_hashes"][path] = "0" * 64
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    with pytest.raises(RuntimeProtocolError, match="escapes"):
        load_tiny_export(tiny_export)


def test_export_refuses_mutable_or_teacher_base_identity(tiny_export: Path) -> None:
    manifest_path = tiny_export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["base_model_identity"]["native_revision"] = "main"
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    with pytest.raises(RuntimeProtocolError, match="admitted student identity"):
        load_tiny_export(tiny_export)


def test_export_requires_passing_parity(tiny_export: Path) -> None:
    manifest_path = tiny_export / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["parity"]["passed"] = False
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    with pytest.raises(RuntimeProtocolError, match="parity"):
        load_tiny_export(tiny_export)
