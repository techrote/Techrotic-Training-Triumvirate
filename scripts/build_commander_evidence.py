"""Seal one completed commander qualification using actual local artifacts.

No inference, ratings generation, publication or deferred gates. The original
programme verifier makes the final decision. Large binaries remain local.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from evaluate_q4_commander import TITAN, verify_export

from techrotic_training_triumvirate.admission import (
    evidence_reference,
    load_package,
    verify_package,
    write_package,
)
from techrotic_training_triumvirate.evaluation.closedloop import (
    verify_closed_loop_report,
)
from techrotic_training_triumvirate.schemas import canonical_json
from techrotic_training_triumvirate.training.admission import (
    load_training_config,
    resolve_model_binding,
)
from techrotic_training_triumvirate.training.campaign_integrity import (
    verify_training_reuse,
)
from techrotic_training_triumvirate.training.data import load_corpus_examples
from techrotic_training_triumvirate.training.export import sha256_file
from techrotic_training_triumvirate.training.model import TrainingMix


def metrics(frozen: dict[str, Any], closed: dict[str, Any]) -> dict[str, Any]:
    """Extract actual results; final package verification also checks frozen sums."""
    replay = verify_closed_loop_report(closed)
    evidence = replay.evidence
    if frozen["policy"] != evidence["policy"]:
        raise ValueError("frozen and long-session policy identities differ")
    episodes = evidence["episodes"]

    def mean(group: str, key: str) -> float:
        return sum(e["metrics"][group][key] for e in episodes) / len(episodes)

    mechanical = frozen["operational"]["mechanical"]
    hidden = frozen["operational"]["hidden_information"]
    values = {
        "mechanical": mechanical["score"],
        "rejection_recovery": mechanical["rejection_recovery_rate"],
        "frozen_commands": sum(c["command_count"] for c in frozen["cases"]),
        "long_objectives": mean("objective", "objective_completion_rate"),
        "long_recovery": mean("recovery", "execution_failure_recovery_rate"),
        "long_schema": mean("objective", "schema_valid_rate"),
        "long_repetition": mean("automated_character_proxies", "repetition_rate"),
        "long_character": {
            k: mean("automated_character_proxies", k)
            for k in episodes[0]["metrics"]["automated_character_proxies"]
        },
        "frozen_critical": hidden["critical_violation_count"],
        "frozen_hidden_fact_use": hidden["hidden_fact_use_count"],
        "long_critical": sum(
            e["metrics"]["hidden_information"]["critical_violation_count"]
            for e in episodes
        ),
    }
    values["passed"] = (
        values["mechanical"] >= 0.95
        and values["rejection_recovery"] >= 0.8
        and values["frozen_commands"] > 0
        and values["long_objectives"] >= 0.8
        and values["long_recovery"] >= 0.8
        and values["long_schema"] >= 0.95
        and values["long_repetition"] <= 0.5
        and values["frozen_critical"]
        == values["frozen_hidden_fact_use"]
        == values["long_critical"]
        == 0
    )
    return values


def verify_runtime_binary(runtime: dict[str, Any], binary: Path) -> None:
    """Measurements must refer to the actual file that will be admitted."""
    if (
        runtime["artifact_sha256"] != sha256_file(binary)
        or runtime["artifact_size_bytes"] != binary.stat().st_size
    ):
        raise ValueError("runtime measurements do not bind the actual Q4 binary")


def relative(root: Path, path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"missing or escaped input: {path}")
    return resolved.relative_to(root).as_posix()


def reporter_identity(root: Path, revision: str) -> dict[str, Any]:
    files = {}
    import techrotic_training_triumvirate.admission as admission_module

    executed = {
        "scripts/build_commander_evidence.py": Path(__file__),
        "src/techrotic_training_triumvirate/admission.py": Path(
            admission_module.__file__
        ),
    }
    for name in (
        "scripts/build_commander_evidence.py",
        "src/techrotic_training_triumvirate/admission.py",
        "docs/rag/19-final-admission.md",
    ):
        committed = subprocess.run(
            ["git", "show", f"{revision}:{name}"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        actual = executed.get(name, root / name)
        if committed.replace(b"\r\n", b"\n") != actual.read_bytes().replace(
            b"\r\n", b"\n"
        ):
            raise ValueError("reporter differs from its declared committed source")
        files[name] = sha256_file(actual)
    return {"reporter_source": revision, "executed_file_sha256": files}


def verify_allocation(ledger: dict[str, Any]) -> None:
    charged = ledger["charged_gpu_hours"]
    if not 0 <= charged <= 22:
        raise ValueError("allocation exceeds the admitted 22-hour cap")
    actual = 0.0
    for attempt in ledger["attempts"]:
        if attempt.get("gpu_uuid", TITAN) != TITAN:
            raise ValueError("allocation contains another physical GPU")
        if (
            type(attempt["status"]) is not int
            and attempt["status"] != "conservative_preflight"
        ):
            raise ValueError("allocation has an unresolved attempt")
        hours = attempt["actual_gpu_hours"]
        if not 0 <= hours <= attempt.get("hours", hours):
            raise ValueError("attempt charge lies outside its reservation")
        actual += hours
    if not math.isclose(actual, charged, abs_tol=1e-8):
        raise ValueError("allocation total differs from attempt charges")


def publish_staged(
    root: Path, output: Path, inputs: dict[str, str], render
) -> dict[str, Any]:
    """Publish a result directory only after isolated strict package readback."""
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root) or output.exists():
        raise ValueError("fresh output directory within the evidence root required")
    output_name = output.relative_to(root)
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    if not artifacts.resolve().is_relative_to(root):
        raise ValueError("artifact staging directory escaped the evidence root")
    stage = Path(
        tempfile.mkdtemp(prefix="commander-evidence-", dir=artifacts)
    ).resolve()
    if not stage.is_relative_to(artifacts.resolve()):
        raise ValueError("staging root escaped artifact directory")
    try:
        for name in inputs:
            if relative(root, root / name) != name:
                raise ValueError("input path is not canonical")
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(root / name, target)
        destination = stage / output_name
        destination.mkdir(parents=True)
        package = render(stage, destination)
        write_package(
            destination / "admission-package.json", package, evidence_root=stage
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        destination.rename(output)
        return verify_package(output / "admission-package.json", evidence_root=root)
    finally:
        if stage.parent != artifacts.resolve() or not stage.name.startswith(
            "commander-evidence-"
        ):
            raise ValueError("refusing escaped staging cleanup")
        shutil.rmtree(stage)


def build(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    output = args.output.resolve()
    if not output.is_relative_to(root) or output.exists():
        raise ValueError("fresh output directory within the evidence root required")
    output_name = output.relative_to(root)
    binding = resolve_model_binding("primary")
    _, dataset = load_corpus_examples(args.corpus)
    corpus = load_package(args.corpus / "manifest.json")
    if (
        sha256_file(args.corpus / "source-episodes.jsonl")
        != corpus["source_archive_sha256"]
    ):
        raise ValueError("source episode archive differs from corpus manifest")
    verified = verify_training_reuse(
        args.training,
        binding=binding,
        config=load_training_config(
            "primary",
            profile_version=2,
            mix=TrainingMix.JOINT_CORRECTIVE,
            seed=24302,
        ),
        dataset=dataset,
        source_revision=args.semantic_source,
    )
    ledger_path = args.training.parent / "allocation-ledger.json"
    ledger = load_package(ledger_path)
    verify_allocation(ledger)
    if (args.training.parent / "allocation.lock").exists():
        raise ValueError("allocation still has an active device lease")
    native_runtime = verified.manifest.runtime
    if (
        native_runtime["gpu_identity"]["actual_cuda_uuid"] != TITAN
        or native_runtime["gpu_identity"]["identity_verified"] is not True
        or native_runtime["budget"]["external_compute_cost_gbp"] != 0
        or native_runtime["budget"]["paid_model_api_cost_gbp"] != 0
    ):
        raise ValueError("native runtime differs from the admitted TITAN-only budget")
    complete = load_package(args.training / "worker-complete.json")
    if complete != {"complete": True, "run_id": verified.result["run_id"]}:
        raise ValueError("native worker completion does not match verified training")
    if sha256_file(args.native_checkpoint) != binding.native_artifact_sha256:
        raise ValueError("native checkpoint bytes differ from admission")
    frozen = load_package(args.evaluation / "benchmark.json")
    closed = load_package(args.evaluation / "closed-loop.json")
    observed = metrics(frozen, closed)
    if not observed["passed"]:
        raise ValueError("candidate fails original operational/character gates")
    runtime = load_package(args.evaluation / "runtime-measurements.json")
    runtime_raw = load_package(args.evaluation / "runtime-raw.json")
    if (
        runtime_raw["gpu_identity"]["actual_cuda_uuid"] != TITAN
        or runtime_raw["gpu_identity"]["identity_verified"] is not True
    ):
        raise ValueError("Q4 runtime did not verify the admitted physical TITAN")
    binary = args.export / "commander-Q4_K_M.gguf"
    verify_runtime_binary(runtime, binary)
    export = verify_export(
        args.export / "export-manifest.json",
        training_root=args.training,
        model=binary,
        semantic_source=args.semantic_source,
    )
    merged = load_package(args.export / "merged/merge-manifest.json")
    if sha256_file(args.export / "commander-f16.gguf") != export["f16_sha256"]:
        raise ValueError("F16 parent differs from export lineage")
    for name, digest in merged["merged_files"].items():
        if sha256_file(args.export / "merged" / name) != digest:
            raise ValueError("merged parent differs from export lineage")
    card = args.data_card.read_text(encoding="utf-8")
    if not all(
        v in card
        for v in (dataset.dataset_hash, dataset.manifest_sha256, args.semantic_source)
    ):
        raise ValueError("data card does not bind this dataset and source")
    human = load_package(args.human_ratings)
    # The strict original verifier validates actual scored fields and candidate ID.
    # This builder never creates scores or infers reviewer identity.
    reporter = reporter_identity(root, args.reporter_source)
    reporter["human_input"] = {
        "path": relative(root, args.human_ratings),
        "sha256": sha256_file(args.human_ratings),
    }
    reporter["allocation_input"] = {
        "path": relative(root, ledger_path),
        "sha256": sha256_file(ledger_path),
    }
    inputs: dict[str, str] = {}

    def include(path: Path, kind: str) -> None:
        name = relative(root, path)
        if name in inputs and inputs[name] != kind:
            raise ValueError("ambiguous evidence kind")
        inputs[name] = kind

    for name, kind in (
        ("benchmark.json", "frozen-evaluation"),
        ("closed-loop.json", "closed-loop"),
        ("runtime-measurements.json", "runtime-measurements"),
        ("candidate-metadata.json", "candidate-metadata"),
        ("raw-generations.jsonl", "raw-generations"),
        ("runtime-raw.json", "runtime-raw"),
        ("server.log", "runtime-log"),
    ):
        include(args.evaluation / name, kind)
    for name, kind in (
        ("run-manifest.json", "run-manifest"),
        ("parity.json", "export-parity"),
        ("training-result.json", "training-result"),
        ("worker-complete.json", "completion"),
        ("development.json", "development"),
        ("candidate-metadata.json", "native-metadata"),
    ):
        include(args.training / name, kind)
    for name in verified.result["artifact_hashes"]:
        if name != "parity.json":
            include(args.training / name, "training-artifact")
    for name in (
        "manifest.json",
        "source-episodes.jsonl",
        "train-00000.jsonl",
        "dev-00000.jsonl",
    ):
        include(args.corpus / name, "corpus")
    for name in (
        "export-manifest.json",
        "commander-f16.gguf",
        "commander-Q4_K_M.gguf",
        "merged/merge-manifest.json",
    ):
        include(args.export / name, "export-lineage")
    for name in merged["merged_files"]:
        include(args.export / "merged" / name, "merged-artifact")
    for name in (
        "human-packet.json",
        "human-packet-key.json",
        "review-packet.md",
        "review-group-key.json",
        "comparison.json",
    ):
        include(args.comparison / name, "blinded-review")
    include(args.native_checkpoint, "admitted-native-binary")
    limitations = [
        "One selected continuation candidate and scripted control; "
        "not a new four-way ablation.",
        "Synthetic English abstract worlds; no downstream game integration claim.",
        "Scripted oracle/templates; no model-generated teacher or "
        "learner-visited training contribution.",
        "Episode/seed splits are disjoint; generator families and "
        "style vocabulary overlap.",
        "Codec, observation coverage, data volume and SFT exposure are confounded.",
        "Automated secrecy and character detectors have limits; "
        "human review has a small sample.",
        "Weights remain local and unpublished. A clean clone must restore "
        "every hash-bound binary before full readback.",
        "Corpus redistribution remains ungranted pending owner licence review; "
        "native LFM licence/notices apply.",
    ]
    candidate_id = frozen["policy"]["policy_id"]
    packet_key = load_package(args.comparison / "human-packet-key.json")
    if not any(v["policy"] == frozen["policy"] for v in packet_key.values()):
        raise ValueError("blinded packet does not include this exact candidate")
    model_card = (
        "# Qualified commander model card\n\n"
        f"Candidate: `{candidate_id}`. Training run: `{verified.result['run_id']}`.\n\n"
        f"Native base: `{binding.native_repository}@{binding.native_revision}`.\n\n"
        f"Semantic source: `{args.semantic_source}`. "
        f"Q4 SHA-256: `{export['q4_sha256']}`.\n\n"
        "Bounded internal research admission uses the unchanged programme gates. "
        "Native reload parity compares actual strings; "
        "Q4 behavior is independently evaluated. "
        "No equality between native and quantized generations is assumed.\n\n"
        + "\n".join(f"- {v}" for v in limitations)
        + "\n"
    )
    report = (
        "# Commander continuation qualification\n\n"
        "Outcome: **ADMITTED**, subject to the scope and limitations below.\n\n"
        f"Semantic source: `{args.semantic_source}`. "
        f"Reporter source: `{args.reporter_source}`.\n\n"
        "The initial TTT-016 negative study and failed continuation attempts "
        "remain historical evidence. "
        "Attempt-03 was rejected on fresh development without a frozen readout. "
        "This result applies to the exact trained Q4 candidate bound here.\n\n"
        "## Operational and automated character results\n\n"
        f"```json\n{json.dumps(observed, indent=2)}\n```\n\n"
        "## Measured Q4 runtime\n\n"
        f"```json\n{json.dumps(runtime, indent=2)}\n```\n\n"
        "## Supplied human ratings\n\n"
        f"```json\n{json.dumps(human, indent=2)}\n```\n\n"
        "Scores are supplied review data. Template adherence and loss "
        "do not substitute for them; "
        "their presence does not establish broad subjective quality.\n\n"
        "## Compute accounting\n\n"
        f"Continuation charge: {ledger['charged_gpu_hours']:.6f} GPU-equivalent "
        "hours against a 22-hour cap, including failures and runtime qualification. "
        "Initial-study consumption is separately preserved (0.962306 hours). "
        "Only the admitted TITAN RTX is selected; no V100, paid API or external "
        "compute is authorized by this package.\n\n"
        "## Limitations\n\n" + "\n".join(f"- {v}" for v in limitations) + "\n"
    )

    def render(stage: Path, destination: Path) -> dict[str, Any]:
        (destination / "data-card.md").write_text(card, encoding="utf-8", newline="\n")
        (destination / "model-card.md").write_text(
            model_card, encoding="utf-8", newline="\n"
        )
        (destination / "report.md").write_text(report, encoding="utf-8", newline="\n")
        (destination / "reporter.json").write_text(
            canonical_json(reporter) + "\n", encoding="utf-8", newline="\n"
        )
        (destination / "human-ratings.json").write_text(
            canonical_json(human) + "\n", encoding="utf-8", newline="\n"
        )
        (destination / "allocation-ledger.json").write_text(
            canonical_json(ledger) + "\n", encoding="utf-8", newline="\n"
        )
        generated = {
            (output_name / name).as_posix(): kind
            for name, kind in (
                ("data-card.md", "data-card"),
                ("model-card.md", "model-card"),
                ("report.md", "comparative-report"),
                ("reporter.json", "reporter-source"),
                ("human-ratings.json", "human-ratings"),
                ("allocation-ledger.json", "compute-accounting"),
            )
        }
        references = {**inputs, **generated}
        package = {
            "schema": "ttt.final_admission",
            "schema_version": 1,
            "programme_id": "TTT-016",
            "code_revision": args.semantic_source,
            "outcome": "ADMITTED",
            "rationale": [
                "Completed continuation passes the unchanged gates with "
                "actual Q4 measurements and supplied human review."
            ],
            "evidence": [
                evidence_reference(stage, name, kind=kind)
                for name, kind in sorted(references.items())
            ],
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "base_model": binding.native_repository
                    + "@"
                    + binding.native_revision,
                    "outcome": "ADMITTED",
                    "model_card": (output_name / "model-card.md").as_posix(),
                    "evidence_refs": sorted(references),
                    "gates": {
                        k: True
                        for k in (
                            "frozen_evaluation",
                            "closed_loop",
                            "hidden_information",
                            "export_parity",
                            "runtime",
                            "provenance",
                            "human_review",
                        )
                    },
                    "constraints": [],
                }
            ],
            "data_card": (output_name / "data-card.md").as_posix(),
            "report": (output_name / "report.md").as_posix(),
            "limitations": limitations,
            "unavailable_artifacts": [],
        }
        return package

    return publish_staged(root, output, inputs, render)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    for name in (
        "training",
        "evaluation",
        "export",
        "corpus",
        "comparison",
        "human-ratings",
        "data-card",
        "native-checkpoint",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--semantic-source", required=True)
    parser.add_argument("--reporter-source", required=True)
    args = parser.parse_args()
    print(canonical_json(build(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
