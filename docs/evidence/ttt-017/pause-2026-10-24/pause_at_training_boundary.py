"""Owned one-run pause: complete training/parity, or preserve a durable checkpoint."""
import json
import math
import os
import shutil
import time
from pathlib import Path

import psutil
from techrotic_training_triumvirate.training.admission import load_training_config, resolve_model_binding
from techrotic_training_triumvirate.training.campaign import write_json
from techrotic_training_triumvirate.training.campaign_integrity import verify_training_reuse
from techrotic_training_triumvirate.training.data import load_corpus_examples
from techrotic_training_triumvirate.training.export import sha256_file
from techrotic_training_triumvirate.training.model import TrainingMix

BASE = Path(__file__).resolve().parent
TRAINING = BASE / "attempt-04"
plan = json.loads((BASE / "pause-request.json").read_text())
owned = plan["worker"]
started = time.monotonic()
elapsed_start = max(0, time.time() - plan["requested_at_unix"])
_, dataset = load_corpus_examples(BASE / "corpus-v4")
config = load_training_config("primary", profile_version=2, mix=TrainingMix.JOINT_CORRECTIVE, seed=24302)
binding = resolve_model_binding("primary")
verified = None
reason = None
checkpoint = None

while True:
    elapsed = elapsed_start + time.monotonic() - started
    try:
        process = psutil.Process(owned["pid"])
        if not math.isclose(process.create_time(), owned["create_time"], abs_tol=.001, rel_tol=0):
            raise RuntimeError("PID was reused; refusing to stop unrelated process")
        if process.cmdline() != owned["command"]:
            raise RuntimeError("owned worker command changed; refusing termination")
    except psutil.NoSuchProcess:
        reason = "worker already terminal before pause control"
        break
    if (TRAINING / "training-result.json").exists():
        verified = verify_training_reuse(TRAINING, binding=binding, config=config,
            dataset=dataset, source_revision=plan["training_source"])
        result = verified.result
        assert result["completed_steps"] == 1473 and result["training_metrics"]["epoch"] == 3.0
        assert result["parity"]["passed"] is True
        assert len(result["parity"]["cases"]) == 3
        assert all(c["pre_export"] == c["post_export"] for c in result["parity"]["cases"])
        if elapsed >= plan["earliest_stop_after_seconds"]:
            reason = "requested completed-training and exact-reload-parity milestone"
            break
    if elapsed >= plan["hard_pause_after_seconds"]:
        candidates = sorted((TRAINING / "checkpoints").glob("checkpoint-*"),
                            key=lambda p:int(p.name.split("-")[-1]), reverse=True)
        for candidate in candidates:
            required = ("trainer_state.json", "optimizer.pt", "scheduler.pt", "rng_state.pth", "adapter_model.safetensors", "adapter_config.json")
            if not all((candidate / n).is_file() and (candidate / n).stat().st_size > 0 for n in required):
                continue
            state = json.loads((candidate / "trainer_state.json").read_text())
            if state["global_step"] != int(candidate.name.split("-")[-1]):
                continue
            checkpoint = candidate
            reason = "requested 30-minute limit; durable optimizer/RNG checkpoint"
            break
        if checkpoint:
            break
    time.sleep(.5)

before_stop = {
    "reason": reason, "worker": owned, "training_complete": verified is not None,
    "checkpoint": str(checkpoint) if checkpoint else None,
    "requested_at_unix": plan["requested_at_unix"], "stop_requested_at_unix": time.time(),
    "watcher_sha256": sha256_file(Path(__file__)), "training_source": plan["training_source"],
}
write_json(BASE / "pause-stop-intent.json", before_stop)
try:
    process = psutil.Process(owned["pid"])
    assert math.isclose(process.create_time(), owned["create_time"], abs_tol=.001, rel_tol=0)
    assert process.cmdline() == owned["command"]
    process.terminate()
    process.wait(timeout=30)
except psutil.NoSuchProcess:
    pass

deadline = time.monotonic() + 60
while (BASE / "allocation.lock").exists() and time.monotonic() < deadline:
    time.sleep(.5)
ledger = json.loads((BASE / "allocation-ledger.json").read_text())
assert not (BASE / "allocation.lock").exists(), "supervisor did not reconcile the device lease"
assert ledger["attempts"][-1]["status"] != "reserved", "supervisor left an unknown charge"

phase = TRAINING / "paused-phase-01"
phase.mkdir()
native_complete = (TRAINING / "worker-complete.json").exists()
if not native_complete:
    for name in ("worker.log", "candidate-metadata.json", "raw-generations.jsonl", "development.json", "benchmark.json", "closed-loop.json"):
        source = TRAINING / name
        if source.exists():
            target = phase / name
            assert source.resolve().is_relative_to(TRAINING.resolve())
            assert target.resolve().is_relative_to(phase.resolve()) and not target.exists()
            source.rename(target)
if checkpoint:
    snapshot = phase / checkpoint.name
    snapshot.mkdir()
    for source in checkpoint.iterdir():
        if source.is_file(): os.link(source, snapshot / source.name)
    checkpoint = snapshot
if verified is None and (TRAINING / "training-result.json").exists():
    verified = verify_training_reuse(TRAINING, binding=binding, config=config,
        dataset=dataset, source_revision=plan["training_source"])
state = {
    **before_stop, "stage": "PAUSED", "paused_at_unix": time.time(),
    "training_complete": verified is not None, "native_evaluation_complete": native_complete,
    "checkpoint_snapshot": str(checkpoint) if checkpoint else None,
    "charged_gpu_hours": ledger["charged_gpu_hours"], "device_lease_released": True,
    "continuation_stopped": True, "phase_archive": str(phase),
    "phase_files": {p.name:sha256_file(p) for p in phase.iterdir() if p.is_file()},
    "training_run": verified.result["run_id"] if verified else None,
    "run_manifest_sha256": sha256_file(TRAINING / "run-manifest.json") if verified else None,
    "adapter_sha256": sha256_file(TRAINING / "adapter/adapter_model.safetensors") if verified else None,
    "admission": "unproven; evaluations/runtime/human review remain required",
}
write_json(BASE / "pause-result.json", state)
write_json(BASE / "qualification-state.json", state)
print(json.dumps(state, indent=2), flush=True)
