"""One explicit experiment continuation; not the general controller planned in #43."""
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from techrotic_training_triumvirate.evaluation.closedloop import (
    ClosedLoopBaseline, run_closed_loop, verify_closed_loop_report, write_closed_loop_comparison,
)
from techrotic_training_triumvirate.training.campaign import write_json
from techrotic_training_triumvirate.training.device_admission import GPUSelection
from techrotic_training_triumvirate.training.export import sha256_file

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
SEMANTIC = "f152cafc59bda5207b8cb1c5ef7d6d60133d1b41"
DRIVER = "ba904aad3c6640b524960f5c2a61dd8b4bc330d9"
SCRIPTS = BASE / f"source-{DRIVER}" / "scripts"
TRAINING = BASE / "attempt-04"
EXPORT = BASE / "export-04"
Q4 = BASE / "q4-04-graphs-disabled"
TITAN = "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8"
PYTHON = ROOT / ".venv-training/Scripts/python.exe"
STATE = BASE / "qualification-state.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def quality(root):
    frozen = load(root / "benchmark.json")
    report = verify_closed_loop_report(load(root / "closed-loop.json"))
    episodes = report.evidence["episodes"]
    mean = lambda group, key: sum(e["metrics"][group][key] for e in episodes) / len(episodes)
    summary = {
        "frozen_mechanical": frozen["operational"]["mechanical"]["score"],
        "frozen_rejection_recovery": frozen["operational"]["mechanical"]["rejection_recovery_rate"],
        "frozen_critical": frozen["operational"]["hidden_information"]["critical_violation_count"],
        "long_objectives": mean("objective", "objective_completion_rate"),
        "long_recovery": mean("recovery", "execution_failure_recovery_rate"),
        "long_schema": mean("objective", "schema_valid_rate"),
        "long_repetition": mean("automated_character_proxies", "repetition_rate"),
        "long_critical": sum(e["metrics"]["hidden_information"]["critical_violation_count"] for e in episodes),
    }
    summary["passed"] = (
        summary["frozen_mechanical"] >= .95 and summary["frozen_rejection_recovery"] >= .8
        and summary["frozen_critical"] == summary["long_critical"] == 0
        and summary["long_objectives"] >= .8 and summary["long_recovery"] >= .8
        and summary["long_schema"] >= .95 and summary["long_repetition"] <= .5)
    return summary


def main():
    own_lock = BASE / "qualification-continuation.lock"
    fd = os.open(own_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w") as stream:
        stream.write(str(os.getpid()))
    try:
        write_json(STATE, {"stage": "WAITING_FOR_NATIVE", "semantic_source": SEMANTIC,
                          "driver_source": DRIVER, "launcher_sha256": sha256_file(Path(__file__))})
        deadline = time.monotonic() + 9000
        while not (TRAINING / "worker-complete.json").exists() or (BASE / "allocation.lock").exists():
            attempts = load(BASE / "allocation-ledger.json")["attempts"]
            attempt = next((a for a in attempts if a.get("output") == str(TRAINING)), None)
            if attempt and attempt["status"] != "reserved" and not (TRAINING / "worker-complete.json").exists():
                raise RuntimeError("native worker failed before complete evidence")
            if time.monotonic() > deadline:
                raise RuntimeError("native continuation wait deadline exhausted")
            time.sleep(10)
        if not (TRAINING / "closed-loop.json").exists():
            write_json(STATE, {"stage": "DEVELOPMENT_REJECTED", "development": load(TRAINING / "development.json")})
            return 1
        native = quality(TRAINING)
        write_json(BASE / "native-quality-summary.json", native)
        if not native["passed"]:
            write_json(STATE, {"stage": "NATIVE_GATE_MISS", "metrics": native})
            return 1
        environment = {**os.environ, "CUDA_VISIBLE_DEVICES": "",
            "PYTHONPATH": str(BASE / f"source-{SEMANTIC}" / "src"), "PYTHONUNBUFFERED": "1"}
        lease = BASE / "allocation.lock"
        fd = os.open(lease, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        try:
            ledger = BASE / "allocation-ledger.json"
            state = load(ledger)
            charged = state["charged_gpu_hours"]
            cap = .5
            if charged + cap > 22:
                raise RuntimeError("runtime reservation would exceed admitted allocation")
            state["charged_gpu_hours"] += cap
            state["attempts"].append({"output": str(Q4), "status": "reserved", "hours": cap,
                "source_revision": SEMANTIC, "driver_source_revision": DRIVER, "gpu_uuid": TITAN})
            write_json(ledger, state)
            write_json(STATE, {"stage": "Q4_QUALIFICATION", "native": native})
            environment = GPUSelection.from_uuid(TITAN).environment(environment)
            started = time.monotonic()
            with (BASE / "q4-04-graphs-disabled-supervisor.log").open("w", encoding="utf-8") as log:
                child = subprocess.run([str(PYTHON), str(SCRIPTS / "evaluate_q4_commander.py"),
                    "--training", str(TRAINING), "--model", str(EXPORT / "commander-Q4_K_M.gguf"),
                    "--export-manifest", str(EXPORT / "export-manifest.json"),
                    "--server", str(BASE / "tools/llama-win/llama-server.exe"),
                    "--output", str(Q4), "--semantic-source", SEMANTIC,
                    "--driver-source", DRIVER, "--disable-cuda-graphs", "--hard-seconds", "1800"], cwd=ROOT,
                    env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=1815)
            actual = min(cap, (time.monotonic() - started) / 3600)
            state["charged_gpu_hours"] = charged + actual
            state["attempts"][-1].update(status=child.returncode, actual_gpu_hours=actual)
            write_json(ledger, state)
            if child.returncode:
                raise RuntimeError(f"Q4 worker failed: {child.returncode}")
        finally:
            lease.unlink(missing_ok=True)
        metrics = quality(Q4)
        runtime = load(Q4 / "runtime-measurements.json")
        runtime_passed = (runtime["context_tokens"] >= 2048 and runtime["artifact_size_bytes"] <= 1_000_000_000
            and runtime["peak_resident_memory_bytes"] <= 3_000_000_000
            and runtime["ttft_seconds"] <= 2 and runtime["decode_tokens_per_second"] >= 12)
        write_json(BASE / "q4-graphs-disabled-quality-summary.json", {"quality": metrics, "runtime_passed": runtime_passed,
                                                     "runtime": runtime})
        if not metrics["passed"] or not runtime_passed:
            write_json(STATE, {"stage": "Q4_GATE_MISS", "metrics": metrics, "runtime": runtime})
            return 1
        baseline = run_closed_loop(ClosedLoopBaseline(), code_revision=SEMANTIC)
        candidate = verify_closed_loop_report(load(Q4 / "closed-loop.json"))
        comparison = BASE / "comparison-04-graphs-disabled"
        write_closed_loop_comparison([baseline, candidate], comparison,
                                     expected_variants=("joint+corrective",))
        write_json(comparison / "scope.json", {"scope": "one continuation candidate plus scripted control; not a new four-way ablation",
            "expected_variants": ["joint+corrective"], "semantic_source": SEMANTIC})
        packet, key = load(comparison / "human-packet.json"), load(comparison / "human-packet-key.json")
        groups = {}
        for sample in packet["samples"]:
            groups.setdefault(key[sample["sample_id"]]["policy"]["policy_id"], []).append(sample)
        identities = list(groups)
        random.Random(24302).shuffle(identities)
        lines = ["# Blinded commander review", "", "Rate each group overall from1Ã¢â‚¬â€œ5 for humour, surprise and distinctiveness.",
            "These are actual recorded speech excerpts. Do not infer outcomes from the speech.", ""]
        mapping = {}
        for index, identity in enumerate(identities):
            letter = chr(ord("A") + index)
            mapping[letter] = identity
            lines.extend([f"## Group {letter}", ""])
            for sample_index, sample in enumerate(groups[identity]):
                lines.extend([f"Session {sample_index + 1}:", ""])
                for excerpt in sample["excerpts"]:
                    lines.extend([f"- Turn {excerpt['turn']}: {' '.join(excerpt['text'])}"])
                lines.append("")
        (comparison / "review-packet.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
        write_json(comparison / "review-group-key.json", mapping)
        write_json(STATE, {"stage": "WAITING_FOR_HUMAN", "native": native,
            "q4": metrics, "runtime": runtime, "packet": str(comparison / "review-packet.md"),
            "admission": "incomplete until genuine supplied ratings and strict final package readback"})
        return 0
    except Exception as error:
        write_json(STATE, {"stage": "CONTINUATION_FAILED", "error": repr(error)})
        raise
    finally:
        own_lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
