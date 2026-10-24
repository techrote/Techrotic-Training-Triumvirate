"""Package portable, verified pilot evidence without publishing model weights."""
import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "worker-source-11e7068" / "src"))
from techrotic_training_triumvirate.training.campaign import verify_completed_worker, prepare_pilot_corpus

REPOSITORY = ROOT.parents[1]
DESTINATION = REPOSITORY / "docs" / "evidence" / "ttt-013-execution"
REVISION = "11e70686b09a27cf7c784beaf8d7a46717b345a0"
VARIANTS = ("prompt-only", "operational", "persona", "joint", "joint+corrective")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


state = json.loads((ROOT / "campaign.json").read_text(encoding="utf-8"))
if state["status"] != "complete" or not state["substantive_campaign_executed"]:
    raise RuntimeError("all five substantive candidates must complete before packaging")
if state["git_commit"] != REVISION:
    raise RuntimeError("unexpected executed source revision")
for variant in VARIANTS:
    if state["variants"][variant]["status"] != "complete":
        raise RuntimeError(f"missing completed candidate: {variant}")
    verify_completed_worker(ROOT / variant.replace("+", "-"), variant=variant, git_commit=REVISION)

packaged = {}


def copy_text(source, target):
    if not source.is_file():
        raise RuntimeError(f"missing required evidence: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8-sig")
    target.write_text(text, encoding="utf-8", newline="\n")
    packaged[source.resolve()] = target.resolve()


DESTINATION.mkdir(parents=True, exist_ok=True)
for name in ("campaign.json", "dependencies.txt", "corpus-identity.json", "continue-titan.py", "supervisor-stop-worker.json", "package-evidence.py"):
    copy_text(ROOT / name, DESTINATION / name)
for name in ("continue-titan-frozen.py", "continuation-stop-worker.json"):
    copy_text(ROOT / name, DESTINATION / name)
copy_text(ROOT / "host-resources.json", DESTINATION / "host-resources.json")
copy_text(ROOT / "preflight.json", DESTINATION / "preflight.json")
for source in sorted((ROOT / "licenses").iterdir()):
    if source.is_file():
        copy_text(source, DESTINATION / "licenses" / source.name)
source_archive = ROOT / "worker-source-11e7068.tar"
if digest(source_archive) != "4ecdb67a5837e99ad1b61f5222a24f60ba01e836befa52c6b5f6ec17cb4da396":
    raise RuntimeError("immutable source archive changed")
with tarfile.open(source_archive) as archive:
    for member in archive.getmembers():
        if member.isfile():
            content = archive.extractfile(member).read()
            extracted = ROOT / "worker-source-11e7068" / member.name
            if extracted.read_bytes() != content:
                raise RuntimeError(f"executed source snapshot changed: {member.name}")
(DESTINATION / source_archive.name).write_bytes(source_archive.read_bytes())
packaged[source_archive.resolve()] = (DESTINATION / source_archive.name).resolve()
for source in sorted((ROOT / "source-audit-live").rglob("*")):
    if source.is_file():
        copy_text(source, DESTINATION / source.relative_to(ROOT))
corpus = ROOT.parent / "pilot-corpus-v2"
regenerated = prepare_pilot_corpus(corpus, seed=750000, episodes_per_tier=12, turns=8, git_commit=REVISION)
if regenerated != json.loads((ROOT / "corpus-identity.json").read_text(encoding="utf-8")):
    raise RuntimeError("corpus regeneration against immutable source changed identity")
for source in sorted(corpus.iterdir()):
    if source.is_file():
        copy_text(source, DESTINATION / "corpus" / source.name)
for source in sorted((ROOT / "failed-attempts").rglob("*")):
    if source.is_file():
        copy_text(source, DESTINATION / source.relative_to(ROOT))

training = {}
generation = {}
for variant in VARIANTS:
    slug = variant.replace("+", "-")
    directory = ROOT / slug
    required = ("benchmark.json", "benchmark.md", "closed-loop.json", "candidate-metadata.json", "raw-generations.jsonl", "worker-result.json", "worker.log")
    if variant != "prompt-only":
        required += ("training-result.json", "run-manifest.json", "training-identity.json", "parity.json")
        training[variant] = json.loads((directory / "training-result.json").read_text())
    for name in required:
        copy_text(directory / name, DESTINATION / slug / name)
    for source in sorted((directory / "adapter").glob("*")):
        if source.is_file() and source.suffix != ".safetensors" and source.stat().st_size <= 262144:
            copy_text(source, DESTINATION / slug / "adapter" / source.name)
    outputs = [json.loads(line) for line in (directory / "raw-generations.jsonl").read_text().splitlines() if line]
    rates = [item["generation_metrics"]["tokens_per_second"] for item in outputs]
    generation[variant] = {
        "action_count": len(outputs),
        "generated_tokens": sum(item["generation_metrics"]["generated_tokens"] for item in outputs),
        "generation_seconds": sum(item["generation_metrics"]["generation_seconds"] for item in outputs),
        "median_tokens_per_second": statistics.median(rates),
        "min_tokens_per_second": min(rates),
        "max_tokens_per_second": max(rates),
    }
    if len(outputs) != 149:
        raise RuntimeError(f"expected all 77 frozen + 72 closed-loop actions for {variant}")

files = []
indexed_sources = set(ROOT.rglob("*")) | set(corpus.rglob("*"))
for source in sorted(indexed_sources):
    if not source.is_file():
        continue
    target = packaged.get(source.resolve())
    files.append({
        "location": source.relative_to(REPOSITORY).as_posix(),
        "sha256": digest(source),
        "size_bytes": source.stat().st_size,
        "packaged": target is not None,
        "portable_path": target.relative_to(DESTINATION).as_posix() if target else None,
        "portable_sha256": digest(target) if target else None,
        "note": "portable text normalized to LF" if target and digest(target) != digest(source) else (("local runtime cache; not packaged" if "__pycache__" in source.parts else "local artifact or duplicated content; not packaged") if not target else "exact bytes"),
    })
write(DESTINATION / "artifact-index.json", {
    "schema": "ttt.pilot_artifact_index", "schema_version": 1,
    "worker_source_revision": REVISION,
    "local_root": "artifacts/ttt-013-execution",
    "local_corpus_root": "artifacts/pilot-corpus-v2",
    "files": files,
})
manifest = json.loads((corpus / "manifest.json").read_text())
budget = {
    "charged_campaign_gpu_hours": state["charged_gpu_hours"],
    "preflight_conservative_gpu_hours": 0.01,
    "total_conservative_gpu_hours": state["charged_gpu_hours"] + 0.01,
    "admitted_pilot_gpu_hours_max": 24.0,
    "requested_campaign_gpu_hours_cap": 4.0,
    "external_compute_cost_gbp": 0.0,
    "paid_model_api_cost_gbp": 0.0,
    "failed_v100_attempt_in_campaign_charge": 0.019123333333312377,
    "operational_and_persona_after_supervisor_stop": "OS creation to observed completion plus 30s conservative guard for each interrupted supervisor",
}
write(DESTINATION / "execution-summary.json", {
    "schema": "ttt.pilot_execution_summary", "schema_version": 1,
    "status": "executed-all-five-candidates", "worker_source_revision": REVISION,
    "corpus_counts": manifest["counts"], "tier_composition": manifest["tier_composition"],
    "corpus_rebuilt_against_archived_source": True,
    "split_distribution": manifest["split_distribution"], "budget": budget,
    "generation": generation,
    "all_completed_candidates_gpu": "NVIDIA TITAN RTX",
    "completed_candidates_gpu_uuid": "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8",
    "runtime_quality_admission": "separate final programme decision; successful execution is not quality admission",
    "limitations": [
        "T2 uses admitted local deterministic style-template teacher enrichment, not live Sprocket/Qwen generation.",
        "The corpus generator reuses ScriptedCommanderBaseline and its Glass-throne/sunrise vocabulary from the reference implementation; no reserved worlds/examples are copied, but persona keyword proxies do not establish held-out-persona generalization.",
        "T3 records scripted student-visited failures and real authoritative corrections, not naturally occurring fine-tuned-student trajectories.",
        "One epoch with a small pilot corpus is not a full-scale training campaign.",
        "Joint has 180 training rows/23 optimizer steps, while the other mixes have 210 rows/27 steps under the same one-epoch profile; content and added-training-exposure effects are not separately identified.",
        "Evaluation private goal remains relay-east while closed-loop mission facts explicitly change priority to ridge-cache; both are visible to all candidates.",
        "Training episodes span eight turns and expose generation through world_state_id (:gN), whereas evaluation adds an explicit observation_generation scalar and stresses prelude/reopen offsets over 24 turns; stale failures characterize this recipe under that distribution shift.",
        "V100 lost before the TITAN-only constraint; its incomplete 42-action prompt attempt is preserved and excluded from candidate comparisons.",
        "Weights and large checkpoint/tokenizer artifacts remain local; artifact-index binds every original file and marks omissions.",
        "The live checkout changed an unused optional LangGraph backend during execution; source-status/patch/file-hash audit is preserved. Remaining workers import the archived immutable source via PYTHONPATH. Reports identify frozen semantic worker code, not a claim that the complete live working tree stayed clean.",
    ],
})
rows = []
for variant in VARIANTS:
    if variant == "prompt-only":
        rows.append("| prompt-only | 0 | 0 | n/a | n/a |")
    else:
        result = training[variant]
        rows.append(f"| {variant} | {result['train_examples']} | {result['completed_steps']} | {result['training_metrics']['train_loss']:.6f} | passed |")
readme = f"""# TTT-013E real native pilot execution

All five candidates completed: the admitted native LFM primary checkpoint
without an adapter, plus operational, persona, joint, and joint+corrective LoRA
variants. Every candidate ran the complete TTT-009 frozen benchmark (77 actions)
and TTT-014 closed-loop suite (72 actions). Execution success does not imply
runtime quality admission; see the final programme decision for the actual gates.

Frozen semantic worker source: `{REVISION}`. Native checkpoint SHA-256:
`1ba63d9adb03ae43581db0e136e4416febe0441aff7296397bd455fb6017f73a`.
Seed 24301 and the admitted model profile are shared across all four fine-tunes.

The corpus contains 36 admitted episodes and 252 examples: T1 96, T2 96, T3 60,
with 210 train and 42 development examples split by scenario family. It contains
zero frozen benchmark examples. Full source episodes, provenance, enrichments,
manifest and exact shards are preserved under `corpus/`.

| Variant | Training examples | Optimizer steps | Training loss | Reload parity |
|---|---:|---:|---:|---|
{chr(10).join(rows)}

All completed candidates ran on NVIDIA TITAN RTX UUID
`GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8`. The initial V100 prompt-only attempt
lost its CUDA device after 42 actions; its complete available outputs, error,
budget snapshot and hardware diagnosis are preserved under `failed-attempts/`.
The owner then required TITAN-only execution. The numeric-index supervisor was
stopped while the healthy TITAN operational worker continued. The recorded
`continue-titan.py` launcher verified the exact CUDA UUID before every remaining
worker and resumed the original budget ledger without changing training or
evaluation code. No reboot or GPU reset was attempted.

The live checkout received an unused optional LangGraph backend typing/lazy-import
patch while processes were active. `source-audit-live/` preserves the complete
status, tracked patch and source hashes at discovery. Training, evaluation,
authority, schema, renderer and recording semantics remained unchanged. This is
an explicit provenance caveat for processes already started; the full working
tree is not claimed to have stayed clean. Remaining workers imported the archived
immutable `worker-source-11e7068.tar` through a checked PYTHONPATH, recorded in
`continue-titan-frozen.py` and the campaign's source provenance override.

The conservative total charged budget is {budget['total_conservative_gpu_hours']:.6f}
GPU-hours, including the failed attempt and 0.01 GPU-hours for preflight. External
compute and paid API costs are both £0. The request cap was four GPU-hours,
within the admitted 24 GPU-hour ceiling. The operational and persona workers whose
supervisors were stopped are charged from their recorded OS process creation
through observed completion plus a 30-second guard each; all other workers use
supervised wall time.

`execution-summary.json` records generation token counts, measured rates and
limitations. T2 is a local deterministic template-teacher contribution with
explicit research provenance; it is not live admitted-model generation. T3 uses
scripted student failures with real authority feedback. The persistent relay goal
and changed closed-loop mission priority are both model-visible and apply equally
to every candidate. The small one-epoch pilot does not establish broad quality.
Joint uses 180 mapped training rows and 23 optimizer steps; the other mixes use
210 rows and 27 steps. The common one-epoch profile therefore compares the
complete dataset mixes and does not isolate extra T3 content from extra exposure.
The scripted corpus policy shares reference-baseline style vocabulary
(`Glass-throne`/`sunrise-vector`). Zero reserved world examples are included;
persona keyword proxies therefore are not evidence of held-out-persona
generalization and must be read alongside repetition and manual ratings.
Training spans eight turns and carries generation in `world_state_id` (`:gN`);
evaluation adds `observation_generation` and tests prelude/reopen offsets over
24 turns. Stale-generation failures apply to this recipe under that shift and
do not establish an intrinsic limit of the admitted model family.

Each candidate directory preserves raw generations and actions, reports,
identity, parity and run metadata. `artifact-index.json` binds every local
checkpoint/adapter file, states what is packaged and records omitted weights.
Large weights remain in the ignored local artifact directory. Logs and dependency
text use portable LF endings; original byte hashes remain in the artifact index.
`licenses/` carries the exact admitted upstream LFM license text, with provenance
and original/portable hashes, alongside the exported tokenizer/adapter metadata.
`SHA256SUMS` covers every portable file except itself, including the completion
marker. No failed result or partial V100 response was silently replaced.
"""
(DESTINATION / "README.md").write_text(readme, encoding="utf-8", newline="\n")
write(DESTINATION / "COMPLETE.json", {
    "schema": "ttt.pilot_evidence_completion", "schema_version": 1,
    "status": "complete", "completed_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "worker_source_revision": REVISION,
    "variants": list(VARIANTS), "all_candidates_frozen_and_closed_loop_evaluated": True,
    "all_completed_candidates_gpu_uuid": "GPU-a8ce1477-4b52-2e8a-350e-6d54c14d1cb8",
    "artifact_index_sha256": digest(DESTINATION / "artifact-index.json"),
    "campaign_sha256": digest(DESTINATION / "campaign.json"),
    "quality_admission": "requires separate final programme decision",
})
checksums = "".join(f"{digest(path)}  {path.relative_to(DESTINATION).as_posix()}\n" for path in sorted(DESTINATION.rglob("*")) if path.is_file() and path.name != "SHA256SUMS")
(DESTINATION / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
for path in DESTINATION.rglob("*"):
    if path.is_file() and path.suffix != ".tar" and b"\r\n" in path.read_bytes():
        raise RuntimeError(f"portable text still contains CRLF: {path}")
print("Portable evidence:", DESTINATION)
print("Conservative budget:", budget)
