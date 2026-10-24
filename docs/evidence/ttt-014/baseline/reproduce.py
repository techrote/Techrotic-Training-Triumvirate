"""Regenerate model-free baseline evidence from the recorded, unchanged sources."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from techrotic_training_triumvirate.evaluation import (
    ScriptedCommanderBaseline,
    load_benchmark_v1,
    run_benchmark,
)
from techrotic_training_triumvirate.evaluation.closedloop import (
    ClosedLoopBaseline,
    run_closed_loop,
    verify_closed_loop_report,
)
from techrotic_training_triumvirate.schemas import canonical_json

SOURCE_REVISION = "11e70686b09a27cf7c784beaf8d7a46717b345a0"
OUTPUT = Path(__file__).resolve().parent
REPOSITORY = OUTPUT.parents[3]


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def source_binding() -> dict[str, object]:
    files = {
        Path(module.__file__).resolve()
        for name, module in sys.modules.copy().items()
        if name.startswith("techrotic_training_triumvirate")
        and getattr(module, "__file__", None)
        and str(module.__file__).endswith(".py")
    }
    files.add(
        REPOSITORY / "src/techrotic_training_triumvirate/evaluation/benchmark_v1.json"
    )
    bindings: dict[str, object] = {}
    for path in sorted(files):
        relative = path.relative_to(REPOSITORY).as_posix()
        committed = subprocess.check_output(
            ["git", "show", f"{SOURCE_REVISION}:{relative}"], cwd=REPOSITORY
        )
        # Windows checkout line endings are a presentation filter. Verify exact
        # normalized source text and also retain the actual executed file digest.
        if path.read_text(encoding="utf-8") != committed.decode("utf-8").replace(
            "\r\n", "\n"
        ):
            raise RuntimeError(f"executed source differs from recorded revision: {relative}")
        bindings[relative] = {
            "git_blob_sha1": subprocess.check_output(
                ["git", "rev-parse", f"{SOURCE_REVISION}:{relative}"], cwd=REPOSITORY,
                text=True,
            ).strip(),
            "executed_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_matches_recorded_commit": True,
        }
    return bindings


def main() -> None:
    metadata = {
        "variant": "scripted",
        "substantive": False,
        "quality_evidence": False,
        "purpose": "deterministic reference control; not native model evidence",
    }
    source_before = source_binding()
    benchmark = run_benchmark(
        ScriptedCommanderBaseline(), code_revision=SOURCE_REVISION
    )
    if benchmark.to_dict() != run_benchmark(
        ScriptedCommanderBaseline(), code_revision=SOURCE_REVISION
    ).to_dict():
        raise RuntimeError("frozen benchmark baseline did not reproduce")
    extended = run_closed_loop(
        ClosedLoopBaseline(), code_revision=SOURCE_REVISION,
        candidate_metadata=metadata, measure_runtime=False,
    )
    repeat = run_closed_loop(
        ClosedLoopBaseline(), code_revision=SOURCE_REVISION,
        candidate_metadata=metadata, measure_runtime=False,
    )
    if extended.evidence != repeat.evidence:
        raise RuntimeError("closed-loop semantic evidence did not reproduce")
    verify_closed_loop_report(extended.to_dict())
    source_after = source_binding()
    if source_before != source_after:
        raise RuntimeError("executed source changed during baseline evaluation")
    write(OUTPUT / "benchmark.json", benchmark.to_json())
    write(OUTPUT / "benchmark.md", benchmark.to_markdown())
    write(OUTPUT / "closed-loop.json", extended.to_json())
    write(OUTPUT / "closed-loop.md", extended.to_markdown())
    manifest = load_benchmark_v1()
    evidence = {
        "schema": "ttt.baseline_evidence",
        "schema_version": 1,
        "source_revision": SOURCE_REVISION,
        "source_binding": source_after,
        "benchmark_id": manifest.benchmark_id,
        "benchmark_version": manifest.benchmark_version,
        "benchmark_hash": manifest.manifest_hash,
        "benchmark_report_hash": benchmark.report_hash(),
        "closed_loop_semantic_hash": extended.semantic_hash(),
        "substantive": False,
        "quality_evidence": False,
        "runtime_measured": False,
        "verification": {
            "frozen_benchmark_reproduced": True,
            "closed_loop_semantics_reproduced": True,
            "closed_loop_authoritative_readback_verified": True,
            "executed_sources_verified_before_and_after": True,
        },
        "invocation": "python docs/evidence/ttt-014/baseline/reproduce.py",
    }
    write(OUTPUT / "evidence-manifest.json", canonical_json(evidence))
    artifacts = sorted(path for path in OUTPUT.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    write(OUTPUT / "SHA256SUMS", "\n".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        for path in artifacts
    ))
    print(json.dumps({
        "source_revision": SOURCE_REVISION,
        "benchmark_report_hash": benchmark.report_hash(),
        "closed_loop_semantic_hash": extended.semantic_hash(),
        "files": [path.name for path in artifacts],
    }, indent=2))


if __name__ == "__main__":
    main()
