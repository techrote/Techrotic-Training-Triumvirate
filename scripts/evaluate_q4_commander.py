"""Evaluate a hash-bound trained Q4 derivative through unchanged TTT semantics.

Use PYTHONPATH pointing to the archived training/evaluation semantic source.
This external HTTP transport has its own source hash, like the pinned runtime.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import platform
import statistics
import subprocess
import threading
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

from techrotic_training_triumvirate.evaluation import PolicyIdentity, run_benchmark
from techrotic_training_triumvirate.evaluation.closedloop import run_closed_loop
from techrotic_training_triumvirate.evaluation.suite import load_benchmark_v1
from techrotic_training_triumvirate.schemas import canonical_json, content_hash
from techrotic_training_triumvirate.training.campaign import write_json
from techrotic_training_triumvirate.training.commander import (
    CODEC,
    SYSTEM,
    commander_input,
    decode_action,
)
from techrotic_training_triumvirate.training.device_admission import (
    GPUSelection,
    verify_cuda_environment,
)
from techrotic_training_triumvirate.training.export import sha256_file

TITAN = "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8"


def verify_sources(semantic_revision: str, driver_revision: str) -> dict[str, Any]:
    """Keep executed semantic modules and this external transport separately bound."""
    records = {}
    sources = [(Path(__file__), "scripts/evaluate_q4_commander.py", driver_revision)]
    for name in ("training.commander", "evaluation.runner", "evaluation.closedloop"):
        module = importlib.import_module("techrotic_training_triumvirate." + name)
        relative = (
            "src/techrotic_training_triumvirate/" + name.replace(".", "/") + ".py"
        )
        sources.append((Path(module.__file__), relative, semantic_revision))
    for path, relative, revision in sources:
        committed = subprocess.run(
            ["git", "show", f"{revision}:{relative}"], check=True, capture_output=True
        ).stdout
        if path.read_bytes().replace(b"\r\n", b"\n") != committed.replace(
            b"\r\n", b"\n"
        ):
            raise ValueError("executed source differs from its declared commit")
        records[relative] = {
            "source_revision": revision,
            "executed_sha256": sha256_file(path),
        }
    return records


def verify_export(
    manifest_path: Path,
    *,
    training_root: Path,
    model: Path,
    semantic_source: str,
) -> dict[str, Any]:
    """Bind the derived Q4 bytes to this exact completed native training run."""
    manifest = json.loads(manifest_path.read_text())
    training = json.loads((training_root / "run-manifest.json").read_text())["payload"]
    merged_path = manifest_path.parent / "merged" / "merge-manifest.json"
    merged = json.loads(merged_path.read_text())
    original = json.loads((training_root / "candidate-metadata.json").read_text())
    expected = {
        "schema": "ttt.q4_commander_export",
        "schema_version": 1,
        "quantization": "Q4_K_M",
        "training_run": original["training_run"],
        "semantic_source": semantic_source,
        "training_manifest_sha256": sha256_file(training_root / "run-manifest.json"),
        "adapter_sha256": sha256_file(
            training_root / "adapter/adapter_model.safetensors"
        ),
        "merged_manifest_sha256": sha256_file(merged_path),
        "q4_sha256": sha256_file(model),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Q4 export source/model/adapter lineage mismatch")
    if (
        training["git_commit"] != semantic_source
        or merged["base_checkpoint"] != original["base_checkpoint"]
        or training["generator_config"]["model_binding"] != original["base_checkpoint"]
        or merged["adapter_files"]["adapter_model.safetensors"]
        != expected["adapter_sha256"]
    ):
        raise ValueError("Q4 native and merged parent identities disagree")
    return manifest


def request(base: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        base + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)


class Q4Adapter:
    def __init__(
        self, base: str, run_id: str, output: Path, expected_model: str | None = None
    ) -> None:
        self.base, self.run_id, self.output = base, run_id, output
        self.expected_model = expected_model
        self.outputs: list[dict[str, Any]] = []

    @property
    def identity(self) -> PolicyIdentity:
        return PolicyIdentity(
            "commander-repair-v2", CODEC + "/llama.cpp-b8185-Q4_K_M", self.run_id
        )

    def begin_case(self, *, case_id: str, seed: int) -> None:
        self.seed = seed

    def act(self, context: Any) -> Any:
        payload = commander_input(context)
        started = time.monotonic()
        response = request(
            self.base,
            {
                "model": self.expected_model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": canonical_json(payload)},
                ],
                "temperature": 0,
                "seed": self.seed,
                "max_tokens": 192,
                "cache_prompt": True,
                "stream": False,
            },
        )
        if (
            self.expected_model is not None
            and response.get("model") != self.expected_model
        ):
            raise ValueError("HTTP response belongs to a different model instance")
        text = response["choices"][0]["message"]["content"]
        action = decode_action(
            text, record_id=f"{context.case_id}:{context.turn_index}"
        )
        row = {
            "case_id": context.case_id,
            "turn": context.turn_index,
            "input_sha256": content_hash(payload),
            "raw_output": text,
            "action": action.to_dict(),
            "wall_seconds": time.monotonic() - started,
            "usage": response.get("usage"),
            "timings": response.get("timings"),
        }
        self.outputs.append(row)
        with (self.output / "raw-generations.jsonl").open(
            "a", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(canonical_json(row) + "\n")
        if len(self.outputs) % 10 == 0:
            print(f"Q4 evaluated {len(self.outputs)} actions", flush=True)
        return action


def measure(base: str) -> list[dict[str, Any]]:
    rows = []
    for index in range(3):
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "In one paragraph, describe why battlefield radio "
                        f"reports need evidence. Example {index}."
                    ),
                }
            ],
            "temperature": 0,
            "seed": 24302 + index,
            "max_tokens": 128,
            "cache_prompt": False,
            "stream": True,
        }
        req = urllib.request.Request(
            base + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        first = None
        pieces = []
        with urllib.request.urlopen(req, timeout=180) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                event = json.loads(line[6:])
                for choice in event.get("choices", []):
                    piece = choice.get("delta", {}).get("content")
                    if piece:
                        first = first if first is not None else time.perf_counter()
                        pieces.append(piece)
        if first is None:
            raise ValueError("runtime produced no actual first token")
        # A non-streamed repeat supplies runtime token accounting and decode timing.
        timed = request(base, {**payload, "stream": False})
        tokens = timed["usage"]["completion_tokens"]
        timings = timed.get("timings", {})
        rate = timings.get("predicted_per_second")
        if not rate:
            raise ValueError("runtime did not expose sustained decode timing")
        rows.append(
            {
                "ttft_seconds": first - started,
                "decode_tokens_per_second": rate,
                "completion_tokens": tokens,
                "response": "".join(pieces),
                "timings": timings,
                "cache_prompt": False,
            }
        )
    return rows


def main() -> int:
    import psutil

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--semantic-source", required=True)
    parser.add_argument("--driver-source", required=True)
    parser.add_argument("--port", type=int, default=18087)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--development-only", action="store_true")
    parser.add_argument("--hard-seconds", type=int, default=1800)
    args = parser.parse_args()
    source_evidence = verify_sources(args.semantic_source, args.driver_source)
    if args.output.exists():
        raise ValueError("fresh evidence output required")
    args.output.mkdir(parents=True)
    environment = GPUSelection.from_uuid(TITAN).environment(os.environ)
    actual = {"mode": "cpu"}
    if args.cpu:
        environment["CUDA_VISIBLE_DEVICES"] = ""
    else:
        if os.environ.get("CUDA_VISIBLE_DEVICES") != TITAN:
            raise ValueError("pin TITAN UUID before importing any CUDA client")
        import torch

        actual = verify_cuda_environment(cuda=torch.cuda, environment=environment)
    training = json.loads((args.training / "training-result.json").read_text())
    original = json.loads((args.training / "candidate-metadata.json").read_text())
    if original["training_run"] != training["run_id"]:
        raise ValueError("model/run identity mismatch")
    export = verify_export(
        args.export_manifest,
        training_root=args.training,
        model=args.model,
        semantic_source=args.semantic_source,
    )
    if sha256_file(args.server) != export["runtime_files"]["llama-server.exe"]:
        raise ValueError(
            "runtime executable differs from the verified export toolchain"
        )
    model_hash = sha256_file(args.model)
    model_alias = "ttt-commander-" + model_hash[:16]
    command = [
        str(args.server.resolve()),
        "--model",
        str(args.model.resolve()),
        "--alias",
        model_alias,
        "--ctx-size",
        "2048",
        "--parallel",
        "1",
        "--jinja",
        "--threads",
        "8",
        "--batch-size",
        "512",
        "--ubatch-size",
        "128",
        "--n-gpu-layers",
        "0" if args.cpu else "99",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    peak_rss = [0]
    stop = threading.Event()
    with (args.output / "server.log").open("w", encoding="utf-8", newline="\n") as log:
        server = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, env=environment
        )

        def hard_stop() -> None:
            if server.poll() is None:
                server.kill()
            os._exit(124)

        watchdog = threading.Timer(args.hard_seconds, hard_stop)
        watchdog.daemon = True
        watchdog.start()
        process = psutil.Process(server.pid)

        def sample() -> None:
            while not stop.wait(0.02):
                with contextlib.suppress(psutil.Error):
                    peak_rss[0] = max(peak_rss[0], process.memory_info().rss)

        monitor = threading.Thread(target=sample, daemon=True)
        monitor.start()
        try:
            base = f"http://127.0.0.1:{args.port}"
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None:
                    raise ValueError("server exited; inspect preserved log")
                try:
                    with urllib.request.urlopen(
                        base + "/health", timeout=2
                    ) as response:
                        if response.status == 200:
                            break
                except (OSError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.5)
            with urllib.request.urlopen(base + "/v1/models", timeout=5) as response:
                advertised = json.load(response)
            if server.poll() is not None or not any(
                item.get("id") == model_alias for item in advertised["data"]
            ):
                raise ValueError(
                    "listening server does not own the expected model alias"
                )
            rows = measure(base)
            write_json(
                args.output / "runtime-raw.json",
                {
                    "samples": rows,
                    "command": command,
                    "gpu_identity": actual,
                    "peak_cpu_rss_bytes": peak_rss[0],
                    "runtime_driver_source": args.driver_source,
                    "runtime_driver_sha256": sha256_file(Path(__file__)),
                    "model_sha256": model_hash,
                    "server_sha256": sha256_file(args.server),
                },
            )
            metadata = {
                **original,
                "quantization": "Q4_K_M",
                "runtime": "llama.cpp-b8185",
                "runtime_driver_source": args.driver_source,
                "runtime_driver_sha256": sha256_file(Path(__file__)),
                "evaluation_semantics_source": args.semantic_source,
                "model_artifact_sha256": model_hash,
                "export_manifest_sha256": sha256_file(args.export_manifest),
                "export_lineage": export,
                "source_evidence": source_evidence,
            }
            adapter = Q4Adapter(base, training["run_id"], args.output, model_alias)
            if args.development_only:
                source = load_benchmark_v1()
                cases = tuple(
                    replace(c, case_id=f"development-{i}", seed=960000 + i)
                    for i, c in enumerate(source.cases)
                )
                manifest = replace(
                    source,
                    benchmark_id="ttt-development-v2",
                    manifest_hash=content_hash(
                        [{"seed": c.seed, "kind": c.kind} for c in cases]
                    ),
                    generated=tuple(c for c in cases if c.suite == "generated"),
                    adversarial=tuple(c for c in cases if c.suite == "adversarial"),
                )
                report = run_benchmark(
                    adapter, code_revision=args.semantic_source, manifest=manifest
                )
                write_json(args.output / "development.json", report.to_dict())
            else:
                report = run_benchmark(adapter, code_revision=args.semantic_source)
                write_json(args.output / "benchmark.json", report.to_dict())
                extended = run_closed_loop(
                    adapter,
                    code_revision=args.semantic_source,
                    candidate_metadata=metadata,
                )
                write_json(args.output / "closed-loop.json", extended.to_dict())
            write_json(args.output / "candidate-metadata.json", metadata)
            write_json(
                args.output / "runtime-measurements.json",
                {
                    "schema": "ttt.runtime_measurements",
                    "schema_version": 1,
                    "candidate_id": adapter.identity.policy_id,
                    "model_role": "primary",
                    "quantization": "Q4_K_M",
                    "host": canonical_json(
                        {
                            "platform": platform.platform(),
                            "gpu": actual,
                            "server_sha256": sha256_file(args.server),
                            "settings": command,
                            "memory_measurement": (
                                "server working-set RSS sampled "
                                "every 20ms; GPU allocations "
                                "separately logged"
                            ),
                        }
                    ),
                    "artifact_sha256": model_hash,
                    "context_tokens": 2048,
                    "artifact_size_bytes": args.model.stat().st_size,
                    "peak_resident_memory_bytes": peak_rss[0],
                    "ttft_seconds": max(row["ttft_seconds"] for row in rows),
                    "decode_tokens_per_second": statistics.median(
                        row["decode_tokens_per_second"] for row in rows
                    ),
                },
            )
        finally:
            watchdog.cancel()
            stop.set()
            if server.poll() is None:
                server.terminate()
                server.wait(timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
