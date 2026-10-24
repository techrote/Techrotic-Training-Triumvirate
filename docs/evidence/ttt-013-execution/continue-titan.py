"""Recorded continuation after the owner's TITAN-only execution constraint.

This launcher does not modify the frozen 11e7068 worker implementation.
"""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

from techrotic_training_triumvirate.training.campaign import (
    verify_completed_worker,
    write_json,
)
from techrotic_training_triumvirate.training.export import sha256_file

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent / "pilot-corpus-v2"
REVISION = "11e70686b09a27cf7c784beaf8d7a46717b345a0"
UUID = "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8"
STATE_PATH = ROOT / "campaign.json"
state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
stopped = json.loads((ROOT / "supervisor-stop-worker.json").read_text(encoding="utf-8-sig"))
supervisor = stopped["ParentProcessId"]
worker_pid = stopped["ProcessId"]
if psutil.pid_exists(supervisor):
    raise RuntimeError("previous numeric-index supervisor is still alive")
state["execution_override"] = {
    "reason": "owner requires only NVIDIA TITAN RTX after V100 device loss",
    "cuda_visible_devices": UUID,
    "actual_uuid_verified_before_every_worker": True,
    "worker_source_revision": REVISION,
    "continuation_launcher_sha256": sha256_file(Path(__file__)),
    "failed_attempt_evidence": "failed-attempts/prompt-only-v100",
    "numeric_index_supervisor_stopped": supervisor,
}
write_json(STATE_PATH, state)
try:
    process = psutil.Process(worker_pid)
    if "operational" not in " ".join(process.cmdline()):
        raise RuntimeError("recorded current worker PID was reused")
    print(f"Waiting for existing TITAN operational worker {worker_pid}", flush=True)
    process.wait(timeout=3000)
except psutil.NoSuchProcess:
    pass

started = datetime.datetime.fromisoformat(stopped["CreationDate"])
elapsed = max(0.0, (datetime.datetime.now(datetime.UTC) - started).total_seconds())
# The original monotonic supervisor ended early. Round its replacement wall
# measurement upward by 30 seconds and retain the original .8h hard cap.
charge = min(0.8, (elapsed + 30.0) / 3600)
try:
    verify_completed_worker(ROOT / "operational", variant="operational", git_commit=REVISION)
    status = "complete"
    error = None
except Exception as exc:
    status = "failed"
    error = f"{type(exc).__name__}: {exc}"
state["charged_gpu_hours"] = state["charged_gpu_hours"] - 0.8 + charge
state["variants"]["operational"] = {
    "status": status,
    "error": error,
    "wall_seconds": elapsed,
    "charged_gpu_hours": charge,
    "charge_method": "OS process creation to observed completion plus 30s guard",
    "worker_log_sha256": sha256_file(ROOT / "operational" / "worker.log"),
    "cuda_visible_devices_at_start": "0 (resolved physical TITAN after V100 loss)",
    "actual_gpu_uuid_confirmed": UUID,
}
lock = ROOT / "campaign.lock"
if lock.exists():
    lock.rename(ROOT / "failed-attempts" / "stopped-supervisor.lock")
write_json(STATE_PATH, state)

variants = ["persona", "joint", "joint+corrective", "prompt-only"]
if status != "complete":
    variants.insert(0, "operational")
for variant in variants:
    directory = ROOT / variant.replace("+", "-")
    directory.mkdir(parents=True, exist_ok=True)
    if variant == "prompt-only":
        archive = ROOT / "failed-attempts" / "prompt-only-v100"
        archive.mkdir(parents=True, exist_ok=True)
        for source in directory.iterdir():
            if source.is_file():
                shutil.copy2(source, archive / source.name)
                source.unlink()
    cap = 0.8
    previous_charge = state["charged_gpu_hours"]
    if previous_charge + cap > 4.0:
        state["status"] = "budget_exhausted"
        write_json(STATE_PATH, state)
        raise SystemExit(2)
    state["charged_gpu_hours"] = previous_charge + cap
    state["variants"][variant] = {"status": "running", "reserved_gpu_hours": cap, "cuda_visible_devices": UUID}
    write_json(STATE_PATH, state)
    environment = dict(os.environ)
    environment["CUDA_VISIBLE_DEVICES"] = UUID
    environment["PYTHONUNBUFFERED"] = "1"
    # Validate the actual selected CUDA device before loading a checkpoint.
    bootstrap = (
        "import os,torch; expected=os.environ['CUDA_VISIBLE_DEVICES']; "
        "assert torch.cuda.device_count()==1, 'exactly one TITAN GPU required'; "
        "actual=str(torch.cuda.get_device_properties(0).uuid); "
        "assert actual==expected.removeprefix('GPU-'), (actual,expected); "
        "assert torch.cuda.get_device_name(0)=='NVIDIA TITAN RTX'; "
        "print('VERIFIED TITAN UUID',actual,flush=True); "
        "from techrotic_training_triumvirate.training.campaign import main; "
        "raise SystemExit(main())"
    )
    command = [
        sys.executable, "-c", bootstrap, "--worker", "--corpus", str(CORPUS),
        "--output", str(directory), "--variant", variant, "--git-commit", REVISION,
        "--seed", "24301", "--gpu-hours", str(cap),
    ]
    began = time.monotonic()
    error = None
    code = None
    with (directory / "worker.log").open("a", encoding="utf-8") as log:
        try:
            result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=cap*3600)
            code = result.returncode
            if code:
                raise RuntimeError(f"worker exited {code}")
            verify_completed_worker(directory, variant=variant, git_commit=REVISION)
            status = "complete"
        except Exception as exc:
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - began
    charged = min(cap, elapsed / 3600)
    state["charged_gpu_hours"] = previous_charge + charged
    state["variants"][variant] = {
        "status": status, "returncode": code, "error": error, "wall_seconds": elapsed,
        "charged_gpu_hours": charged, "cuda_visible_devices": UUID,
        "worker_log_sha256": sha256_file(directory / "worker.log"),
    }
    state["substantive_campaign_executed"] = any((ROOT / mix / "training-result.json").exists() for mix in ("operational","persona","joint","joint-corrective"))
    write_json(STATE_PATH, state)
    print(variant, status, "charged GPU-hours", state["charged_gpu_hours"], flush=True)
state["status"] = "complete" if all(v["status"]=="complete" for v in state["variants"].values()) and len(state["variants"])==5 else "incomplete"
write_json(STATE_PATH, state)
print("Final campaign status:", state["status"], flush=True)
