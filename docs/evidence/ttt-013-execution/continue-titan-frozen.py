"""Continue UUID-pinned workers using the archived immutable 11e7068 sources."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parent
FROZEN_SOURCE = ROOT / "worker-source-11e7068" / "src"
sys.path.insert(0, str(FROZEN_SOURCE))
from techrotic_training_triumvirate.training.campaign import verify_completed_worker, write_json
from techrotic_training_triumvirate.training.export import sha256_file

CORPUS = ROOT.parent / "pilot-corpus-v2"
REVISION = "11e70686b09a27cf7c784beaf8d7a46717b345a0"
UUID = "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8"
STATE_PATH = ROOT / "campaign.json"
state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
stopped = json.loads((ROOT / "continuation-stop-worker.json").read_text(encoding="utf-8-sig"))
if psutil.pid_exists(stopped["ParentProcessId"]):
    raise RuntimeError("previous continuation supervisor is still alive")
state["source_provenance_override"] = {
    "reason": "live tree includes an unused optional LangGraph backend typing/lazy-import patch after source freeze",
    "working_tree_fully_clean": False,
    "audit": "source-audit-live/audit.json",
    "audit_sha256": sha256_file(ROOT / "source-audit-live" / "audit.json"),
    "worker_source_revision": REVISION,
    "remaining_worker_pythonpath": "worker-source-11e7068/src",
    "source_archive_sha256": sha256_file(ROOT / "worker-source-11e7068.tar"),
    "continuation_launcher_sha256": sha256_file(Path(__file__)),
    "existing_candidate_disposition": "semantic modules unchanged; preserve exact live-tree import caveat for already started processes",
}
write_json(STATE_PATH, state)
try:
    process = psutil.Process(stopped["ProcessId"])
    if "persona" not in " ".join(process.cmdline()):
        raise RuntimeError("current persona worker PID was reused")
    print("Waiting for existing TITAN persona worker", process.pid, flush=True)
    process.wait(timeout=3000)
except psutil.NoSuchProcess:
    pass
elapsed = max(0.0, (datetime.datetime.now(datetime.UTC) - datetime.datetime.fromisoformat(stopped["CreationDate"])).total_seconds())
charge = min(0.8, (elapsed + 30.0) / 3600)
try:
    verify_completed_worker(ROOT / "persona", variant="persona", git_commit=REVISION)
    status, error = "complete", None
except Exception as exc:
    status, error = "failed", f"{type(exc).__name__}: {exc}"
state["charged_gpu_hours"] = state["charged_gpu_hours"] - 0.8 + charge
state["variants"]["persona"] = {
    "status": status, "error": error, "wall_seconds": elapsed,
    "charged_gpu_hours": charge,
    "charge_method": "OS process creation to observed completion plus 30s guard",
    "cuda_visible_devices": UUID,
    "worker_log_sha256": sha256_file(ROOT / "persona" / "worker.log"),
    "source_import_disposition": "started before frozen-source continuation; live audit preserved",
}
write_json(STATE_PATH, state)
variants = ["joint", "joint+corrective", "prompt-only"]
if status != "complete": variants.insert(0, "persona")
for variant in variants:
    directory = ROOT / variant.replace("+", "-")
    directory.mkdir(parents=True, exist_ok=True)
    if variant == "prompt-only":
        archive = ROOT / "failed-attempts" / "prompt-only-v100"
        for source in directory.iterdir():
            if source.is_file():
                shutil.copy2(source, archive / source.name)
                source.unlink()
    cap, previous_charge = 0.8, state["charged_gpu_hours"]
    if previous_charge + cap > 4.0:
        state["status"] = "budget_exhausted"
        write_json(STATE_PATH, state)
        raise SystemExit(2)
    state["charged_gpu_hours"] = previous_charge + cap
    state["variants"][variant] = {"status": "running", "reserved_gpu_hours": cap, "cuda_visible_devices": UUID, "source_snapshot": "worker-source-11e7068/src"}
    write_json(STATE_PATH, state)
    environment = dict(os.environ)
    environment.update(CUDA_VISIBLE_DEVICES=UUID, PYTHONUNBUFFERED="1", PYTHONPATH=str(FROZEN_SOURCE), TTT_FROZEN_SOURCE=str(FROZEN_SOURCE))
    bootstrap = (
        "import os,torch; from pathlib import Path; expected=os.environ['CUDA_VISIBLE_DEVICES']; "
        "assert torch.cuda.device_count()==1; actual=str(torch.cuda.get_device_properties(0).uuid); "
        "assert actual==expected.removeprefix('GPU-'), (actual,expected); "
        "assert torch.cuda.get_device_name(0)=='NVIDIA TITAN RTX'; "
        "print('VERIFIED TITAN UUID',actual,flush=True); "
        "import techrotic_training_triumvirate.training.campaign as campaign; "
        "assert Path(campaign.__file__).resolve().is_relative_to(Path(os.environ['TTT_FROZEN_SOURCE']).resolve()); "
        "print('VERIFIED FROZEN SOURCE',campaign.__file__,flush=True); raise SystemExit(campaign.main())"
    )
    command = [sys.executable,"-c",bootstrap,"--worker","--corpus",str(CORPUS),"--output",str(directory),"--variant",variant,"--git-commit",REVISION,"--seed","24301","--gpu-hours",str(cap)]
    began, code, error = time.monotonic(), None, None
    with (directory / "worker.log").open("a",encoding="utf-8") as log:
        try:
            result = subprocess.run(command,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=cap*3600)
            code = result.returncode
            if code: raise RuntimeError(f"worker exited {code}")
            verify_completed_worker(directory,variant=variant,git_commit=REVISION)
            status = "complete"
        except Exception as exc:
            status,error = "failed",f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic()-began
    state["charged_gpu_hours"] = previous_charge + min(cap,elapsed/3600)
    state["variants"][variant] = {"status":status,"returncode":code,"error":error,"wall_seconds":elapsed,"charged_gpu_hours":min(cap,elapsed/3600),"cuda_visible_devices":UUID,"source_snapshot":"worker-source-11e7068/src","worker_log_sha256":sha256_file(directory/'worker.log')}
    state["substantive_campaign_executed"] = True
    write_json(STATE_PATH,state)
    print(variant,status,"charged GPU-hours",state["charged_gpu_hours"],flush=True)
state["status"] = "complete" if all(v["status"]=="complete" for v in state["variants"].values()) and len(state["variants"])==5 else "incomplete"
write_json(STATE_PATH,state)
print("Final campaign status:",state["status"],flush=True)
