"""Read completed local/portable evidence and build the final negative/qualified report.

This script runs no inference, downloads, training, or publication. It refuses to
write results until all five actual workers and the portable snapshot verify.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from techrotic_training_triumvirate.admission import (
    AdmissionPackageError,
    evidence_reference,
    load_package,
    write_package,
)
from techrotic_training_triumvirate.determinism import seeded_rng
from techrotic_training_triumvirate.evaluation import load_benchmark_v1
from techrotic_training_triumvirate.evaluation.closedloop import (
    ClosedLoopReport,
    verify_closed_loop_report,
)
from techrotic_training_triumvirate.schemas import canonical_json, content_hash
from techrotic_training_triumvirate.session import SessionTurn
from techrotic_training_triumvirate.training.campaign import verify_completed_worker
from techrotic_training_triumvirate.training.data import load_corpus_examples

SOURCE_REVISION = "11e70686b09a27cf7c784beaf8d7a46717b345a0"
VARIANTS = ("prompt-only", "operational", "persona", "joint", "joint+corrective")
PORTABLE = Path("docs/evidence/ttt-013-execution")
LOCAL = Path("artifacts/ttt-013-execution")
BASELINE = Path("docs/evidence/ttt-014/baseline")
COMPARISON = Path("docs/evidence/ttt-014/comparison")
FINAL = Path("docs/evidence/ttt-016")


class FinalEvidenceError(ValueError):
    """Incomplete or corrupt evidence cannot produce a final scientific report."""


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def reporter_source(root: Path) -> dict[str, Any]:
    """Bind reporting tools to their later commit without relabelling workers."""
    revision_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    revision = revision_result.stdout.decode("ascii").strip()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise FinalEvidenceError("reporting source must have an immutable Git commit")
    files, committed_files = {}, {}
    for name in (
        "scripts/build_final_evidence.py",
        "src/techrotic_training_triumvirate/admission.py",
        "docs/rag/19-final-admission.md",
    ):
        committed = subprocess.run(
            ["git", "show", f"{revision}:{name}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        checked_out = (root / name).read_bytes()
        if committed.returncode or committed.stdout.replace(
            b"\r\n", b"\n"
        ) != checked_out.replace(b"\r\n", b"\n"):
            raise FinalEvidenceError(
                f"reporting source is uncommitted or changed: {name}"
            )
        files[name] = sha256(root / name)
        committed_files[name] = hashlib.sha256(committed.stdout).hexdigest()
    return {
        "schema": "ttt.final_evidence_generation",
        "schema_version": 1,
        "worker_source_revision": SOURCE_REVISION,
        "reporting_source_revision": revision,
        "reporting_file_sha256": files,
        "committed_reporting_file_sha256": committed_files,
        "reporting_source_matches_commit_after_crlf_normalization": True,
        "execution": (
            "read-only evidence verification and document generation; no inference"
        ),
    }


def safe_file(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in name
        or ":" in name
        or relative.as_posix() != name
        or name == "."
    ):
        raise FinalEvidenceError(f"unsafe evidence path: {name}")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise FinalEvidenceError(f"missing or escaped evidence: {name}")
    return path


def verify_checksums(directory: Path) -> None:
    """Check actual bytes and require coverage of every file in the snapshot."""
    checksum_file = directory / "SHA256SUMS"
    if not checksum_file.is_file():
        raise FinalEvidenceError(f"missing SHA256SUMS: {directory}")
    seen: set[str] = set()
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        try:
            digest, name = line.split("  ", 1)
        except ValueError as exc:
            raise FinalEvidenceError("invalid SHA256SUMS line") from exc
        if (
            len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
            or name in seen
            or name == "SHA256SUMS"
        ):
            raise FinalEvidenceError("invalid or duplicate checksum entry")
        if sha256(safe_file(directory, name)) != digest:
            raise FinalEvidenceError(f"artifact hash mismatch: {name}")
        seen.add(name)
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != checksum_file
    }
    if seen != actual:
        raise FinalEvidenceError("SHA256SUMS does not cover the exact snapshot")


def summarize_candidate(
    frozen: dict[str, Any],
    closed: ClosedLoopReport,
    metadata: dict[str, Any],
    training: dict[str, Any] | None,
) -> dict[str, Any]:
    """Derive declared gates from observed results; never impute human/Q4 data."""
    episodes = closed.evidence["episodes"]
    groups = [episode["metrics"] for episode in episodes]

    def average(group: str, key: str) -> float:
        return sum(float(item[group][key]) for item in groups) / len(groups)

    mechanical = frozen["operational"]["mechanical"]
    frozen_hidden = frozen["operational"]["hidden_information"]
    hidden_counts = {
        key: sum(int(item["hidden_information"][key]) for item in groups)
        for key in (
            "secret_leakage_count",
            "hidden_world_fact_text_match_count",
            "fabricated_result_count",
            "intercept_grounding_failure_count",
            "critical_violation_count",
        )
    }
    objective = average("objective", "objective_completion_rate")
    recovery = average("recovery", "execution_failure_recovery_rate")
    command_count = sum(case["command_count"] for case in frozen["cases"])
    accepted_count = sum(case["accepted_count"] for case in frozen["cases"])
    parity = training["parity"]["passed"] is True if training else None
    gates = {
        "frozen_evaluation": mechanical["score"] >= 0.95
        and mechanical["rejection_recovery_rate"] >= 0.8
        and command_count > 0,
        "closed_loop": objective >= 0.8 and recovery >= 0.8,
        "hidden_information": frozen_hidden["critical_violation_count"] == 0
        and frozen_hidden["hidden_fact_use_count"] == 0
        and hidden_counts["critical_violation_count"] == 0,
        "export_parity": parity is True,
        "runtime": False,
        "provenance": True,
        "human_review": False,
    }
    return {
        "variant": metadata["variant"],
        "policy": frozen["policy"],
        "metadata": metadata,
        "gates": gates,
        "mechanical_score": mechanical["score"],
        "frozen_mechanical": mechanical,
        "frozen_command_count": command_count,
        "frozen_accepted_command_count": accepted_count,
        "frozen_schema_valid_rate": mechanical["parse_valid_rate"],
        "rejection_recovery_rate": mechanical["rejection_recovery_rate"],
        "frozen_hidden_information": frozen_hidden,
        "frozen_closed_loop": frozen["operational"]["closed_loop"],
        "closed_loop_objective_rate": objective,
        "closed_loop_failure_recovery_rate": recovery,
        "closed_loop_schema_valid_rate": average("objective", "schema_valid_rate"),
        "closed_loop_acceptance_rate": average("objective", "accepted_command_rate"),
        "closed_loop_churn_rate": average("objective", "churn_rate"),
        "closed_loop_energy_used": sum(
            item["objective"]["energy_used"] for item in groups
        ),
        "closed_loop_hidden_information": hidden_counts,
        "character": {
            key: average("automated_character_proxies", key)
            for key in groups[0]["automated_character_proxies"]
        },
        "closed_loop_communication_count": sum(
            len(SessionTurn.from_dict(turn["session_turn"]).action.communications)
            for episode in episodes
            for turn in episode.get("turns", [])
        ),
        "frozen_character": frozen["character"]["automated_proxies"],
        "native_inference_runtime": closed.runtime,
        "training": None
        if training is None
        else {
            key: training[key]
            for key in (
                "run_id",
                "completed_steps",
                "train_examples",
                "training_metrics",
                "wall_seconds",
                "run_manifest_sha256",
            )
        },
        "human_ratings": {"humour": None, "surprise": None, "distinctiveness": None},
        "q4_runtime_measurements": None,
        "closed_loop_semantic_hash": closed.semantic_hash(),
    }


def _read_completed(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[ClosedLoopReport]]:
    portable = root / PORTABLE
    if not (portable / "COMPLETE.json").is_file():
        raise FinalEvidenceError(
            "portable COMPLETE.json is absent; actual campaign is incomplete"
        )
    verify_checksums(portable)
    verify_checksums(root / BASELINE)
    campaign = load_package(portable / "campaign.json")
    if (
        campaign.get("git_commit") != SOURCE_REVISION
        or campaign.get("status") != "complete"
        or campaign.get("substantive_campaign_executed") is not True
        or set(campaign.get("variants", {})) != set(VARIANTS)
        or any(
            campaign["variants"][variant].get("status") != "complete"
            for variant in VARIANTS
        )
    ):
        raise FinalEvidenceError("all five source-bound workers must actually complete")
    execution_summary = load_package(portable / "execution-summary.json")
    budget = execution_summary["budget"]
    if (
        execution_summary.get("worker_source_revision") != SOURCE_REVISION
        or execution_summary.get("status") != "executed-all-five-candidates"
        or abs(
            budget["total_conservative_gpu_hours"]
            - budget["charged_campaign_gpu_hours"]
            - budget["preflight_conservative_gpu_hours"]
        )
        > 1e-9
        or budget["charged_campaign_gpu_hours"] != campaign["charged_gpu_hours"]
    ):
        raise FinalEvidenceError("execution summary source/budget contradicts campaign")
    campaign["evidence_execution_summary"] = execution_summary
    verify_checksums(root / COMPARISON)
    comparison = load_package(root / COMPARISON / "comparison.json")
    if (
        comparison.get("substantive_comparison_complete") is not True
        or comparison.get("missing_real_variants") != []
        or len(comparison.get("candidates", [])) != 6
    ):
        raise FinalEvidenceError(
            "TTT-014 comparison must include baseline and all five real variants"
        )
    corpus, dataset = load_corpus_examples(portable / "corpus")
    if (
        not corpus
        or dataset.dataset_hash != campaign["plan"]["dataset_identity"]["dataset_hash"]
    ):
        raise FinalEvidenceError("portable corpus identity contradicts campaign")
    index = load_package(portable / "artifact-index.json")
    if (
        index.get("schema") != "ttt.pilot_artifact_index"
        or index.get("worker_source_revision") != SOURCE_REVISION
        or not isinstance(index.get("files"), list)
    ):
        raise FinalEvidenceError("invalid local/portable artifact index")
    for item in index["files"]:
        path = safe_file(root, item["location"])
        if path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]:
            raise FinalEvidenceError(
                f"local artifact no longer matches index: {item['location']}"
            )
        if item["packaged"]:
            packaged = safe_file(portable, item["portable_path"])
            if sha256(packaged) != item["portable_sha256"]:
                raise FinalEvidenceError("portable artifact contradicts index")
    summaries, reports = [], []
    expected_raw_count = sum(case.turns for case in load_benchmark_v1().cases) + 72
    for variant in VARIANTS:
        slug = variant.replace("+", "-")
        local, copied = root / LOCAL / slug, portable / slug
        verify_completed_worker(
            local,
            variant=variant,
            git_commit=SOURCE_REVISION,
            dataset=dataset,
            seed=24301,
        )
        required = [
            "benchmark.json",
            "closed-loop.json",
            "candidate-metadata.json",
            "worker-result.json",
        ]
        if variant != "prompt-only":
            required.extend(
                [
                    "training-result.json",
                    "run-manifest.json",
                    "training-identity.json",
                    "parity.json",
                ]
            )
        for name in required:
            if sha256(local / name) != sha256(copied / name):
                raise FinalEvidenceError(
                    f"portable worker report differs from original: {slug}/{name}"
                )
        frozen = load_package(copied / "benchmark.json")
        extended = verify_closed_loop_report(load_package(copied / "closed-loop.json"))
        metadata = load_package(copied / "candidate-metadata.json")
        if (
            metadata["dataset_hash"] != dataset.dataset_hash
            or frozen["policy"] != extended.evidence["policy"]
        ):
            raise FinalEvidenceError("candidate dataset/policy identity changed")
        raw = [
            json.loads(line)
            for line in (copied / "raw-generations.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        if len(raw) != expected_raw_count:
            raise FinalEvidenceError(f"incomplete raw generation evidence: {variant}")
        training = (
            load_package(copied / "training-result.json")
            if variant != "prompt-only"
            else None
        )
        summary = summarize_candidate(frozen, extended, metadata, training)
        summary["raw_generation_count"] = len(raw)
        summary["native_generation"] = execution_summary["generation"][variant]
        if training:
            manifest = load_package(copied / "run-manifest.json")
            summary["native_training_runtime"] = manifest["payload"]["runtime"]
        summaries.append(summary)
        reports.append(extended)
    baseline = verify_closed_loop_report(
        load_package(root / BASELINE / "closed-loop.json")
    )
    if {item["semantic_hash"] for item in comparison["candidates"]} != {
        baseline.semantic_hash(),
        *(report.semantic_hash() for report in reports),
    }:
        raise FinalEvidenceError(
            "TTT-014 comparison does not bind these exact worker traces"
        )
    return campaign, summaries, reports


def _recommendation(summary: dict[str, Any]) -> str:
    missed = [
        key
        for key in (
            "frozen_evaluation",
            "closed_loop",
            "hidden_information",
            "export_parity",
            "provenance",
        )
        if not summary["gates"][key]
    ]
    if missed:
        return (
            "Reject continued runtime integration: " + ", ".join(missed) + " gate miss."
        )
    return (
        "Operational evidence supports further qualification; human/Q4 and "
        "portable binary availability remain unqualified."
    )


def _card(summary: dict[str, Any], unavailable: list[str]) -> str:
    metadata, training = summary["metadata"], summary["training"]
    return "\n".join(
        [
            f"# Candidate model card: {summary['policy']['policy_id']}",
            "",
            "**NOT ADMITTED** for runtime integration.",
            "",
            _recommendation(summary),
            "",
            f"- Variant: `{summary['variant']}`; run: `{training['run_id']}`.",
            f"- Executed source commit: `{SOURCE_REVISION}`.",
            f"- Base checkpoint: `{canonical_json(metadata['base_checkpoint'])}`.",
            f"- Dataset SHA-256: `{metadata['dataset_hash']}`.",
            f"- Decoding: `{canonical_json(metadata['decoding'])}`.",
            (
                "- Native Transformers/PEFT float32 execution; Q4 export and target "
                "runtime measurements absent."
            ),
            f"- Mechanical/rejection recovery: {summary['mechanical_score']:.6f} / "
            f"{summary['rejection_recovery_rate']:.6f}.",
            "- Long-session objective/failure recovery: "
            f"{summary['closed_loop_objective_rate']:.6f} / "
            f"{summary['closed_loop_failure_recovery_rate']:.6f}.",
            "- Hidden-information detections: "
            f"`{canonical_json(summary['closed_loop_hidden_information'])}`.",
            f"- Character proxies: `{canonical_json(summary['character'])}`.",
            f"- Gate dispositions: `{canonical_json(summary['gates'])}`.",
            f"- Training metrics: `{canonical_json(training)}`.",
            "- Native training host/memory: "
            f"`{canonical_json(summary.get('native_training_runtime'))}`.",
            "- Native inference wall timing: "
            f"`{canonical_json(summary['native_inference_runtime'])}`.",
            "",
            (
                "Humour, surprise and distinctiveness human ratings remain null. "
                "Training loss and parity are not quality scores."
            ),
            "",
            (
                "Local binaries/checkpoints are hash-indexed but are not included "
                "in this portable package or published externally:"
            ),
            *[f"- `{path}`" for path in unavailable],
            "",
            (
                "The base model remains subject to LFM Open License v1.0. Project "
                "corpus redistribution permission is ungranted pending owner "
                "review; see data-card.md."
            ),
            "",
            (
                "Limitations: small template-driven corpus; scripted T3 source "
                "policy; fixed relay private goal despite observed changing "
                "priority; conservative lexical secret detector; no CyberSand "
                "integration."
            ),
            (
                "Import provenance: initial workers used the live checkout while "
                "the unrelated optional LangGraph backend received typing/lazy-import "
                "changes. A source audit preserves those changes; no full-tree-clean "
                "claim is made. Later workers use the packaged source11e archive "
                "with verified campaign import path. See the report and source audit."
            ),
            "",
        ]
    )


def _human_packet(
    reports: list[ClosedLoopReport],
) -> tuple[dict[str, Any], dict[str, Any]]:
    samples, key = [], {}
    for report in reports:
        for episode in report.evidence["episodes"]:
            identity = {
                "policy": report.evidence["policy"],
                "case_id": episode["case_id"],
            }
            sample_id = content_hash(identity)[:16]
            excerpts = []
            for record in episode["turns"][:4]:
                turn = SessionTurn.from_dict(record["session_turn"])
                excerpts.append(
                    {
                        "turn": turn.turn_id,
                        "text": [item.text for item in turn.action.communications],
                    }
                )
            samples.append(
                {
                    "sample_id": sample_id,
                    "excerpts": excerpts,
                    "human_ratings": {
                        "humour": None,
                        "surprise": None,
                        "distinctiveness": None,
                        "comments": None,
                    },
                }
            )
            key[sample_id] = identity
    seeded_rng(24301).shuffle(samples)
    return {
        "schema": "ttt.blinded_rating_packet",
        "scale": "1-5; unfilled until rated by a human",
        "samples": samples,
    }, key


def report_tables(
    summaries: list[dict[str, Any]], baseline_frozen: dict[str, Any]
) -> list[str]:
    lines = [
        "# Initial TTT programme comparative report",
        "",
        (
            "**Programme outcome: NOT ADMITTED.** All five actual native-checkpoint "
            "workers completed; the four trained candidates remain unqualified for "
            "runtime integration."
        ),
        "",
        f"Executed source: `{SOURCE_REVISION}`. Frozen suites and held-out "
        "scenario reservations were retained; no benchmark response "
        "was added to training.",
        "",
        (
            "| Policy | Frozen mechanical | Rejection recovery | 24-turn objectives "
            "| Failure recovery | Critical detections |"
        ),
        "|---|---:|---:|---:|---:|---:|",
        "| Scripted reference | "
        f"{baseline_frozen['operational']['mechanical']['score']:.6f} | "
        "1.000 | 1.000 | 1.000 | 0 |",
    ]
    for item in summaries:
        critical = (
            item["closed_loop_hidden_information"]["critical_violation_count"]
            + item["frozen_hidden_information"]["critical_violation_count"]
        )
        lines.append(
            f"| {item['variant']} | {item['mechanical_score']:.6f} | "
            f"{item['rejection_recovery_rate']:.6f} | "
            f"{item['closed_loop_objective_rate']:.6f} | "
            f"{item['closed_loop_failure_recovery_rate']:.6f} | **{critical}** |"
        )
    lines.extend(
        [
            "",
            "| Policy | Frozen accepted / commands | Frozen schema valid | "
            "Long-session acceptance | Churn | Energy used |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in summaries:
        lines.append(
            f"| {item['variant']} | {item['frozen_accepted_command_count']} / "
            f"{item['frozen_command_count']} | "
            f"{item['frozen_schema_valid_rate']:.6f} | "
            f"{item['closed_loop_acceptance_rate']:.6f} | "
            f"{item['closed_loop_churn_rate']:.6f} | "
            f"{item['closed_loop_energy_used']} |"
        )
    lines.extend(
        [
            "",
            "Frozen aggregate mechanical submetrics have empty-denominator and "
            "upstream-rejection conventions: downstream entity/precondition rates can "
            "remain high when schema validation already rejected a command, and a "
            "no-command policy can obtain default rates of one. Raw schema, accepted "
            "counts, objectives and recovery must be inspected with the score. The "
            "builder treats zero total commands as missing mechanical execution "
            "evidence and does not pass that gate. The immutable reported metrics "
            "are preserved without retrospective rescoring.",
        ]
    )
    lines.extend(
        [
            "",
            "Critical detections sum frozen and long-session counts. "
            "Detailed secrecy groups retain exact secret matches, lexical world-fact "
            "matches, fabricated-result markers and intercept failures separately.",
            "",
            "| Policy | Speech emissions | Persona constraints | Repetition proxy | "
            "Lexical diversity | Doctrine consistency | Native action seconds | "
            "Native median tok/s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in summaries:
        character = item["character"]
        duration = item["native_inference_runtime"]["total_action_seconds"]
        token_rate = item.get("native_generation", {}).get("median_tokens_per_second")
        token_label = f"{token_rate:.3f}" if token_rate is not None else "unmeasured"
        lines.append(
            f"| {item['variant']} | {item['closed_loop_communication_count']} | "
            f"{character['constraint_adherence_rate']:.6f} | "
            f"{character['repetition_rate']:.6f} | "
            f"{character['lexical_diversity']:.6f} | "
            f"{character['doctrine_consistency_rate']:.6f} | {duration:.3f} | "
            f"{token_label} |"
        )
    lines.extend(
        [
            "",
            "Repetition is the mean of per-episode automated proxies; an empty "
            "speech episode has proxy 1. Thus a high mean with one total utterance "
            "does not imply that utterance was repeated. Native action seconds cover "
            "the 72 long-session actions; native median token rates use all 149 saved "
            "generations in the execution summary. They do not qualify Q4 runtime.",
        ]
    )
    lines.extend(["", "Automated style warnings (proxies, not human quality scores):"])
    for item in summaries:
        if item["closed_loop_communication_count"] == 0:
            lines.append(f"- {item['variant']}: no long-session speech emissions.")
        elif item["character"]["repetition_rate"] > 0.5:
            lines.append(
                f"- {item['variant']}: episode-averaged repetition proxy exceeds "
                "0.50 (including the empty-episode convention)."
            )

    return lines


def build_final_evidence(root: Path) -> dict[str, Any]:
    """Write only after complete evidence validation; leave data-card.md intact."""
    root = root.resolve()
    campaign, summaries, reports = _read_completed(root)
    reporting = reporter_source(root)
    destination = root / FINAL
    if not (destination / "data-card.md").is_file():
        raise FinalEvidenceError("root-authored data card is required")
    card_text = (destination / "data-card.md").read_text(encoding="utf-8")
    for digest in (
        campaign["plan"]["dataset_identity"]["dataset_hash"],
        sha256(root / PORTABLE / "corpus" / "manifest.json"),
        sha256(root / PORTABLE / "corpus" / "source-episodes.jsonl"),
    ):
        if digest not in card_text:
            raise FinalEvidenceError(
                "root-authored data card does not match actual corpus"
            )
    index = load_package(root / PORTABLE / "artifact-index.json")
    omitted = [
        item["location"]
        for item in index["files"]
        if not item["packaged"]
        and ("/adapter/" in item["location"] or "/checkpoints/" in item["location"])
    ]
    if not omitted:
        raise FinalEvidenceError(
            "expected explicit omitted local model/checkpoint artifacts"
        )
    baseline = verify_closed_loop_report(
        load_package(root / BASELINE / "closed-loop.json")
    )
    baseline_frozen = load_package(root / BASELINE / "benchmark.json")
    packet, key = _human_packet([baseline, *reports])
    for name, value in (
        ("generation-manifest.json", reporting),
        (
            "comparative-metrics.json",
            {"source_revision": SOURCE_REVISION, "candidates": summaries},
        ),
        ("human-packet.json", packet),
        ("human-packet-key.json", key),
    ):
        (destination / name).write_text(
            canonical_json(value) + "\n", encoding="utf-8", newline="\n"
        )
    trained = [item for item in summaries if item["variant"] != "prompt-only"]
    budget = campaign["evidence_execution_summary"]["budget"]
    for item in trained:
        slug = item["variant"].replace("+", "-")
        local = [path for path in omitted if f"/{slug}/" in path]
        (destination / f"model-card-{slug}.md").write_text(
            _card(item, local), encoding="utf-8", newline="\n"
        )
    lines = report_tables(summaries, baseline_frozen)
    lines.extend(
        [
            "",
            "Reporting tools source commit: "
            f"`{reporting['reporting_source_revision']}`. "
            "This later reporting commit is separate from the unchanged worker source "
            f"`{SOURCE_REVISION}`; generation-manifest.json binds both identities.",
        ]
    )
    lines.extend(["", "## Candidate decisions", ""])
    for item in trained:
        lines.append(f"- **{item['variant']}: NOT ADMITTED.** {_recommendation(item)}")
    lines.extend(
        [
            "",
            (
                "Prompt-only is an actual admitted-base comparison, with no "
                "fine-tuning or export-parity claim. Deterministic baseline results "
                "validate the harness; they are not model-quality evidence."
            ),
            "",
            "## Character, runtime and human evidence",
            "",
            (
                "`comparative-metrics.json` separates command "
                "validity/recovery/objectives, churn/energy, secrecy, "
                "lexical/persona proxies, native wall timing, native training "
                "memory and loss. Per-turn actions and raw generations remain in "
                "the hashed portable worker evidence. "
                "Operational-only/persona-only/joint differences are inspectable "
                "there; empty speech is not assigned humour or distinctiveness."
            ),
            (
                "Human humour, surprise and distinctiveness ratings remain "
                "**null**. The seeded blinded packet is ready for review; its "
                "identity key is separate. No human result is fabricated."
            ),
            (
                "Q4 size, resident memory, TTFT, token throughput and quantization "
                "degradation were **not measured for these trained adapters**. "
                "Native GPU training peaks and action wall time do not fill those "
                "original runtime gates. The challenger was not trained in this "
                "pilot."
            ),
            "",
            "## Execution, reproducibility and limits",
            "",
            f"- Campaign host: `{canonical_json(campaign['host'])}`.",
            "- Total conservative GPU hours including preflight: "
            f"`{budget['total_conservative_gpu_hours']}` "
            f"(campaign `{budget['charged_campaign_gpu_hours']}` + "
            f"preflight `{budget['preflight_conservative_gpu_hours']}`). "
            "The failed V100 charge is already included in the campaign amount; "
            f"external compute: £{campaign['external_compute_cost_gbp']}; "
            f"paid API spend: £{campaign['paid_model_api_cost_gbp']}.",
            (
                "- The first prompt-only attempt lost the V100 after 42 raw "
                "responses. Its original log, generations, failure records and "
                "budget charge remain preserved. The interrupted numeric-index "
                "supervisor was stopped. Continuation used the owner's TITAN "
                "RTX-only constraint with UUID assertion before each unchanged "
                "source-bound worker; no machine reboot or failure erasure "
                "occurred."
            ),
            "- Execution override: "
            f"`{canonical_json(campaign.get('execution_override'))}`.",
            (
                "- Import provenance caveat: initial workers imported from the live "
                "checkout while the optional LangGraph backend received typing/lazy-"
                "import changes. The portable source-audit-live directory preserves "
                "the live status, patch and source hashes; this report makes no "
                "full-tree-clean claim. Campaign, training, evaluation, world, "
                "schema, renderer and recording semantics remained source11e. "
                "Remaining workers imported from the packaged source11e archive "
                "under a verified campaign module path. Archive/launcher/audit bytes "
                "are bound in the portable snapshot and final package."
            ),
            (
                f"- {sum(item['gates']['export_parity'] for item in trained)}/4 "
                "exports passed their recorded fixed-fixture save/reload "
                "checks. This is native PEFT parity, not a "
                "GGUF/quantization export."
            ),
            (
                "- Corpus/model provenance, exact splits, checkpoint identities, "
                "decoding, dependency capture, launcher, logs, source episodes and "
                "raw responses are hashed. Large adapter/checkpoint files remain "
                "local and explicitly unavailable in the portable package; no model "
                "publication occurred. The artifact index also records unpacked "
                "source-cache/duplicate-output omissions reconstructible from the "
                "packaged source archive/raw records; those are not classified as "
                "unavailable model/checkpoint artifacts."
            ),
            (
                "- The corpus has 252 examples (210 train / 42 dev), deterministic "
                "local style templates and scripted T3 errors. It does not "
                "establish emergent humour or broad tactical generalization."
            ),
            (
                "- The inference private goal remains relay-east while admitted "
                "observations announce changing priorities. This prompt "
                "inconsistency may affect adaptation and is preserved as an "
                "experimental limitation."
            ),
            (
                "- The conservative world-fact matcher can flag the substring "
                "reserve inside preserve; inspect flagged speech/commands before "
                "interpreting matches as confirmed semantic disclosure. Exact "
                "operation-code disclosures and authority markers remain "
                "prominently counted. Zero detections does not prove absence of "
                "paraphrased or encoded leakage."
            ),
            (
                "- Frozen failures remain evaluation-only. Next experiments should "
                "repair observed command/recovery limitations with new training "
                "identities, expand learner-visited recovery and independent "
                "tactical families, then rerun the frozen suite and obtain human/Q4 "
                "qualification. CyberSand integration remains deferred."
            ),
            "",
        ]
    )
    (destination / "report.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )
    references = []
    for directory in (root / PORTABLE, root / BASELINE, root / COMPARISON, destination):
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.name == "admission-package.json":
                continue
            if directory == destination and (
                path.name.startswith("admission-package") or path.name == "SHA256SUMS"
            ):
                continue
            kind = {
                "benchmark.json": "frozen-evaluation",
                "closed-loop.json": "closed-loop",
                "run-manifest.json": "run-manifest",
                "parity.json": "export-parity",
            }.get(path.name, "provenance")
            if directory == root / COMPARISON and path.name.startswith("candidate-"):
                kind = "closed-loop"
            references.append(
                evidence_reference(root, path.relative_to(root).as_posix(), kind=kind)
            )
    all_paths = [reference["path"] for reference in references]
    candidates = []
    for item in trained:
        slug = item["variant"].replace("+", "-")
        candidates.append(
            {
                "candidate_id": item["policy"]["policy_id"],
                "base_model": item["metadata"]["base_checkpoint"]["native_repository"],
                "outcome": "NOT ADMITTED",
                "model_card": (FINAL / f"model-card-{slug}.md").as_posix(),
                "evidence_refs": [
                    name
                    for name in all_paths
                    if name.startswith((PORTABLE / slug).as_posix() + "/")
                    or name == (PORTABLE / "artifact-index.json").as_posix()
                    or name.startswith((PORTABLE / "corpus").as_posix() + "/")
                ],
                "gates": item["gates"],
                "constraints": [],
            }
        )
    package = {
        "schema": "ttt.final_admission",
        "schema_version": 1,
        "programme_id": "TTT-016",
        "code_revision": SOURCE_REVISION,
        "outcome": "NOT ADMITTED",
        "rationale": [
            (
                "Read the candidate-specific gate results; no deployment "
                "qualification is inferred from training loss or parity."
            ),
            (
                "Human ratings and trained-candidate Q4 measurements are absent; "
                "adapter/checkpoint binaries are explicitly unavailable in the "
                "portable package."
            ),
        ],
        "evidence": references,
        "candidates": candidates,
        "data_card": (FINAL / "data-card.md").as_posix(),
        "report": (FINAL / "report.md").as_posix(),
        "limitations": [
            "Small scripted/template-driven corpus and T3 source policy.",
            (
                "No challenger training, trained Q4 qualification or supplied human "
                "ratings."
            ),
            (
                "Fixed relay private goal and conservative lexical hidden-fact "
                "detector; inspect detailed report."
            ),
        ],
        "unavailable_artifacts": omitted,
    }
    if reporter_source(root) != reporting:
        raise FinalEvidenceError("reporting source changed during evidence generation")
    result = write_package(
        destination / "admission-package.json", package, evidence_root=root
    )
    checksums = [
        f"{sha256(path)}  {path.relative_to(destination).as_posix()}"
        for path in sorted(destination.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (destination / "SHA256SUMS").write_text(
        "\n".join(checksums) + "\n", encoding="utf-8", newline="\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    try:
        print(canonical_json(build_final_evidence(args.root)))
    except (
        FinalEvidenceError,
        AdmissionPackageError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        parser.exit(1, f"Final evidence build refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
