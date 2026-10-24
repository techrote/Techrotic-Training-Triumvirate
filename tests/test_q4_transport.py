"""The opt-in HTTP transport preserves model decisions and export lineage."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from techrotic_training_triumvirate.training.export import sha256_file


def transport():
    path = Path(__file__).resolve().parents[1] / "scripts/evaluate_q4_commander.py"
    spec = importlib.util.spec_from_file_location("q4_transport_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_http_transport_does_not_stamp_a_current_generation_or_choose_tactics(
    tmp_path: Path, monkeypatch
) -> None:
    module = transport()
    calls = []
    raw = json.dumps(
        {
            "command": {
                "op": "hold",
                "unit_id": "wrong-unit",
                "observation_generation": 999,
            },
            "speech": "Listen for evidence.",
        }
    )

    def reply(base, payload):
        calls.append(payload)
        return {"choices": [{"message": {"content": raw}}]}

    monkeypatch.setattr(module, "request", reply)
    adapter = module.Q4Adapter("http://localhost", "actual-run-id", tmp_path)
    adapter.begin_case(case_id="test", seed=1)
    context = SimpleNamespace(
        case_id="test",
        turn_index=2,
        observation_generation=3,
        observation=SimpleNamespace(
            facts={"visible": True},
            visible_entities=("unit-1",),
            objective_ids=("relay-east",),
        ),
        persona=SimpleNamespace(to_dict=lambda: {}),
        previous_results=(),
        recent_events=(),
    )
    action = adapter.act(context)
    assert action.commands[0].body == json.loads(raw)["command"]
    assert json.loads(calls[0]["messages"][1]["content"])["observation_generation"] == 3
    assert calls[0]["temperature"] == 0
    assert (
        "response_format" not in calls[0]
    )  # No grammar or oracle repair masks failure.
    assert adapter.outputs[0]["raw_output"] == raw


def test_q4_bytes_and_adapter_must_match_the_recorded_export(tmp_path: Path) -> None:
    module = transport()
    training, export = tmp_path / "training", tmp_path / "export"
    (training / "adapter").mkdir(parents=True)
    (export / "merged").mkdir(parents=True)
    adapter = training / "adapter/adapter_model.safetensors"
    model = export / "model.gguf"
    adapter.write_bytes(b"synthetic-adapter")
    model.write_bytes(b"synthetic-Q4-artifact")
    binding = {"test": "synthetic fixture only"}
    (training / "run-manifest.json").write_text(
        json.dumps(
            {
                "payload": {
                    "git_commit": "a" * 40,
                    "generator_config": {"model_binding": binding},
                }
            }
        )
    )
    (training / "candidate-metadata.json").write_text(
        json.dumps({"training_run": "fixture", "base_checkpoint": binding})
    )
    merged = export / "merged/merge-manifest.json"
    merged.write_text(
        json.dumps(
            {
                "base_checkpoint": binding,
                "adapter_files": {"adapter_model.safetensors": sha256_file(adapter)},
            }
        )
    )
    manifest = export / "export-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "ttt.q4_commander_export",
                "schema_version": 1,
                "quantization": "Q4_K_M",
                "training_run": "fixture",
                "semantic_source": "a" * 40,
                "training_manifest_sha256": sha256_file(training / "run-manifest.json"),
                "adapter_sha256": sha256_file(adapter),
                "merged_manifest_sha256": sha256_file(merged),
                "q4_sha256": sha256_file(model),
            }
        )
    )
    module.verify_export(
        manifest, training_root=training, model=model, semantic_source="a" * 40
    )
    adapter.write_bytes(b"replaced-adapter")
    with pytest.raises(ValueError, match="lineage mismatch"):
        module.verify_export(
            manifest, training_root=training, model=model, semantic_source="a" * 40
        )


def test_http_response_from_wrong_model_is_refused(tmp_path: Path, monkeypatch) -> None:
    module = transport()
    monkeypatch.setattr(module, "request", lambda *args: {"model": "other-model"})
    adapter = module.Q4Adapter("http://localhost", "run", tmp_path, "expected-model")
    adapter.begin_case(case_id="test", seed=1)
    context = SimpleNamespace(
        case_id="test",
        turn_index=0,
        observation_generation=0,
        observation=SimpleNamespace(facts={}, visible_entities=(), objective_ids=()),
        persona=SimpleNamespace(to_dict=lambda: {}),
        previous_results=(),
        recent_events=(),
    )
    with pytest.raises(ValueError, match="different model instance"):
        adapter.act(context)
