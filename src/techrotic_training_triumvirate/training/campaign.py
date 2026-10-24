"""Bounded, resumable real-checkpoint pilot execution (outside default CI).

The orchestration module is dependency-free. Heavy imports occur only in a worker
process after admission; its wall-time cap conservatively counts as GPU time.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import cast

from techrotic_training_triumvirate.commands import CommandInterpreter
from techrotic_training_triumvirate.corpus import (
    CorpusConfig,
    CorpusSource,
    CorpusTier,
    TeacherEnrichment,
    assemble_corpus,
    write_corpus,
)
from techrotic_training_triumvirate.evaluation import (
    EvaluationContext,
    PolicyIdentity,
    ScriptedCommanderBaseline,
    frozen_evaluation_guard,
    run_benchmark,
)
from techrotic_training_triumvirate.schemas import (
    AssistantAction,
    AuthoritativeEvent,
    CommandEnvelope,
    CommanderPrivateContext,
    EpisodeRecord,
    EvaluationAnnotations,
    InterpreterResult,
    JsonObject,
    JsonValue,
    PersonaSpec,
    SourceProvenance,
    TurnRecord,
    canonical_json,
    content_hash,
    load_record,
)
from techrotic_training_triumvirate.session import DeterministicRenderer
from techrotic_training_triumvirate.world import (
    ScenarioConfig,
    ScenarioGenerator,
    WorldAuthority,
)

from .admission import load_training_config, resolve_model_binding
from .data import load_corpus_examples, map_dataset, map_source_example
from .export import sha256_file
from .model import BudgetAuthorization, ModelBinding, SourceExample, TrainingMix
from .pilot import PILOT_MIXES, build_pilot_plan


class CampaignError(ValueError):
    """An execution or resume violated the admitted campaign identity."""


def write_json(path: Path, value: JsonObject) -> None:
    """Replace a small evidence record atomically, preserving real newlines."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def collect_host() -> JsonObject:
    """Record hardware without initializing CUDA or importing ML libraries."""

    probe = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,memory.total,driver_version",
            "--format=csv,noheader",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "gpu_inventory": probe.stdout.strip(),
        "gpu_probe_returncode": probe.returncode,
        "gpu_probe_stderr": probe.stderr.strip(),
    }


def _persona(index: int) -> PersonaSpec:
    archetypes = ("measured", "eccentric", "resolute", "dry")
    return PersonaSpec(
        persona_id=f"pilot-persona-{index % len(archetypes)}",
        archetype=archetypes[index % len(archetypes)],
        traits={"tempo": archetypes[index % len(archetypes)]},
        speech_constraints=("Do not disclose hidden world facts.",),
        doctrine={"command": "verify authoritative feedback before correcting"},
        secret_ids=(),
        tactical_biases={},
    )


def _episode(
    seed: int, tier: CorpusTier, *, turns: int, git_commit: str
) -> CorpusSource:
    """Generate a real authority-backed rollout with explicit source provenance."""

    blueprint = ScenarioGenerator().generate(
        seed=seed, config=ScenarioConfig(complexity=seed % 5 + 1)
    )
    frozen_evaluation_guard().assert_training_allowed(
        family=blueprint.scenario.identity.family, seed=seed
    )
    world = WorldAuthority(blueprint)
    initial = world.world_private_reference()
    interpreter = CommandInterpreter()
    renderer = DeterministicRenderer()
    policy = ScriptedCommanderBaseline()
    persona = _persona(seed)
    run_id = f"pilot-{tier.value.lower()}-{seed}"
    policy.begin_case(case_id=run_id, seed=seed)
    previous_results: tuple[InterpreterResult, ...] = ()
    recent_events: tuple[AuthoritativeEvent, ...] = ()
    records: list[TurnRecord] = []
    for turn in range(turns):
        observation = world.commander_observation(turn_id=turn)
        player_observation = world.player_observation(turn_id=turn)
        context = EvaluationContext(
            case_id=run_id,
            turn_index=turn,
            observation_generation=world.observation_generation,
            observation=observation,
            structured_observation=renderer.structured_observation(observation),
            compact_observation=renderer.compact_observation(observation),
            previous_results=previous_results,
            recent_events=recent_events,
            persona=persona,
        )
        action = policy.act(context)
        if tier is CorpusTier.T3 and turn % 3 == 0:
            # A scripted student visits an invalid entity/stale/schema failure;
            # the following turn is corrected using actual interpreter feedback.
            failure_bodies: tuple[JsonObject, ...] = (
                {"op": "hold", "unit_id": "missing-unit"},
                {"op": "hold", "unit_id": "unit-1", "observation_generation": 999},
                {"op": "hold", "unit_id": "absent-unit"},
            )
            body = dict(failure_bodies[(seed + turn) % len(failure_bodies)])
            body.setdefault("observation_generation", world.observation_generation)
            action = AssistantAction(
                commands=(
                    CommandEnvelope(
                        command_id=f"{run_id}:failed:{turn}",
                        protocol_version="ttt-command-v1",
                        body=body,
                    ),
                ),
                communications=(),
            )
        styles = (
            "Steady hands. Verify, then advance.",
            "The brass kettle whistles; keep the squad together.",
            "Anchor the line. Confirm the relay before moving.",
            "A tidy plan survives its first correction.",
        )
        if action.communications:
            action = replace(
                action,
                communications=tuple(
                    replace(item, text=f"{styles[seed % 4]} {item.text}")
                    for item in action.communications
                ),
            )
        events_start = len(world.events)
        results = []
        for command in action.commands:
            outcome = interpreter.interpret(command, world)
            results.append(outcome.result)
            if outcome.dispatch_event is not None:
                world.events.append(outcome.dispatch_event)
        world.step()
        events = tuple(world.events[events_start:])
        previous_results = tuple(results)
        recent_events = events
        records.append(
            TurnRecord(
                turn_id=turn,
                observation=observation,
                commander_private_context=CommanderPrivateContext(
                    commander_id=run_id,
                    goals=tuple(blueprint.scenario.objective_ids),
                    secret_ids=(),
                    beliefs={},
                    memory_refs=(),
                ),
                assistant_action=action,
                interpreter_results=previous_results,
                world_events=events,
                next_observation=world.commander_observation(turn_id=turn + 1),
                player_observation=player_observation,
                player_intercepts=(),
                annotations=EvaluationAnnotations(labels={}, evaluator_only={}),
            )
        )
    episode = EpisodeRecord(
        episode_id=run_id,
        scenario=blueprint.scenario,
        persona=persona,
        initial_world=initial,
        turns=tuple(records),
        final_world_hash=world.state_hash(),
        run_id=run_id,
    )
    source_id = f"{run_id}:source"
    provenance = SourceProvenance(
        source_id=source_id,
        source_class="hand-authored",
        uri=None,
        revision=git_commit,
        license_id="LicenseRef-Project-Internal-Research",
        source_content_hash=episode.content_hash(),
        metadata={
            "generator": "pilot-authority-script-v1",
            "teacher_kind": "deterministic-local-style-template",
            "license_disposition": "admitted",
            "training_permission": "owner-authorized internal project research",
            "redistribution_permission": "ungranted; owner license review required",
            "model_generated": False,
        },
    )
    enrichments = (
        tuple(
            TeacherEnrichment(
                source_id=source_id,
                turn_id=record.turn_id,
                operational_facts={},
                style_text=styles[seed % 4],
            )
            for record in records
        )
        if tier is CorpusTier.T2
        else ()
    )
    return CorpusSource(
        episode=episode,
        tier=tier,
        provenance=(provenance,),
        teacher_enrichments=enrichments,
    )


def prepare_pilot_corpus(
    output: str | Path,
    *,
    seed: int = 750000,
    episodes_per_tier: int = 12,
    turns: int = 8,
    git_commit: str = "working-tree",
) -> JsonObject:
    """Build benchmark-clean T1/T2/T3 episodes, refusing silently missing tiers."""

    if episodes_per_tier < 2 or turns < 2:
        raise CampaignError(
            "pilot requires at least two episodes per tier and two turns"
        )
    sources = tuple(
        _episode(
            seed + tier_index * 1000 + index, tier, turns=turns, git_commit=git_commit
        )
        for tier_index, tier in enumerate((CorpusTier.T1, CorpusTier.T2, CorpusTier.T3))
        for index in range(episodes_per_tier)
    )
    build = assemble_corpus(sources, config=CorpusConfig(seed=seed + 1, dev_percent=20))
    if build.quarantine:
        issues = [issue.code for item in build.quarantine for issue in item.issues]
        raise CampaignError(f"pilot source quarantine: {issues}")
    root = Path(output)
    archive_content = "".join(
        canonical_json(
            {
                "episode": source.episode.to_dict(),
                "tier": source.tier.value,
                "provenance": [item.to_dict() for item in source.provenance],
                "teacher_enrichments": [
                    {
                        "source_id": item.source_id,
                        "turn_id": item.turn_id,
                        "operational_facts": item.operational_facts,
                        "style_text": item.style_text,
                    }
                    for item in source.teacher_enrichments
                ],
            }
        )
        + "\n"
        for source in sources
    )
    import hashlib

    build.manifest["pilot_source_archive"] = {
        "name": "source-episodes.jsonl",
        "sha256": hashlib.sha256(archive_content.encode()).hexdigest(),
        "episode_count": len(sources),
    }
    if (root / "manifest.json").exists():
        if json.loads((root / "manifest.json").read_text()) != build.manifest:
            raise CampaignError("existing pilot corpus differs; choose a fresh output")
        archive = root / "source-episodes.jsonl"
        if (
            not archive.is_file()
            or sha256_file(archive)
            != hashlib.sha256(archive_content.encode()).hexdigest()
        ):
            raise CampaignError("existing canonical source archive changed")
    else:
        write_corpus(build, root)
        (root / "source-episodes.jsonl").write_text(
            archive_content, encoding="utf-8", newline="\n"
        )
    # This validates tiers, actual shard hashes and the immutable benchmark guard.
    plan = build_pilot_plan(root, external_compute_cost_gbp=0.0)
    return cast(JsonObject, plan["dataset_identity"])


def parse_model_action(text: str, *, command_id: str) -> AssistantAction:
    """Parse exact model JSON; malformed output becomes an observable rejection."""

    try:
        value = json.loads(text)
        if not isinstance(value, dict) or set(value) != {"commands", "communications"}:
            raise ValueError("expected commands/communications payload")
        return cast(
            AssistantAction,
            load_record(
                {
                    "schema": "ttt.assistant_action",
                    "schema_version": 1,
                    "payload": value,
                },
                expected_type=AssistantAction,
            ),
        )
    except (ValueError, TypeError, KeyError):
        return AssistantAction(
            commands=(
                CommandEnvelope(
                    command_id=command_id,
                    protocol_version="ttt-command-v1",
                    body={"op": "invalid_model_output"},
                ),
            ),
            communications=(),
        )


def evaluation_source(
    context: EvaluationContext, previous_action: AssistantAction | None
) -> SourceExample:
    """Project every admitted feedback channel from the evaluation context."""

    private_context = CommanderPrivateContext(
        commander_id="pilot-student",
        goals=("relay-east",),
        secret_ids=(),
        beliefs={},
        memory_refs=(),
    )
    payload: JsonObject = {
        "observation": context.observation.to_dict(),
        "observation_generation": context.observation_generation,
        "commander_private_context": private_context.to_dict(),
        "persona": context.persona.to_dict(),
        "interpreter_results": [r.to_dict() for r in context.previous_results],
        "world_events": [e.to_dict() for e in context.recent_events],
    }
    rejected = any(not result.accepted for result in context.previous_results)
    execution_failed = any(e.kind == "execution-failed" for e in context.recent_events)
    if previous_action is not None and rejected:
        payload["prior_failure"] = {
            "assistant_action": previous_action.to_dict(),
            "interpreter_results": [r.to_dict() for r in context.previous_results],
            "world_events": [e.to_dict() for e in context.recent_events],
        }
    recovering = rejected or execution_failed
    return SourceExample(
        example_id=f"{context.case_id}:{context.turn_index}",
        split="dev",
        tier="T3" if recovering else "T1",
        mode="recovery" if recovering else "standard",
        input=payload,
        target={"commands": [{"placeholder": True}], "communications": []},
    )


class HFStudentAdapter:
    """Native checkpoint + optional LoRA adapter with retained raw output evidence."""

    def __init__(
        self,
        binding: ModelBinding,
        *,
        adapter_dir: str | Path | None,
        variant: str,
        revision: str,
        max_new_tokens: int = 384,
        raw_output_path: Path | None = None,
    ) -> None:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
        from .hf_peft import verify_native_checkpoint

        verify_native_checkpoint(binding)
        self._identity = PolicyIdentity(
            policy_id=f"pilot-{variant.replace('+', '-')}",
            adapter_id="hf-peft-native-v1",
            revision=revision,
        )
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            binding.native_repository, revision=binding.native_revision
        )
        self.model = transformers.AutoModelForCausalLM.from_pretrained(
            binding.native_repository,
            revision=binding.native_revision,
            torch_dtype=torch.float32,
            attn_implementation="eager",
        )
        if adapter_dir is not None:
            peft = importlib.import_module("peft")
            self.model = peft.PeftModel.from_pretrained(self.model, str(adapter_dir))
        self.model.to("cuda")
        self.model.eval()
        self.max_new_tokens = max_new_tokens
        self.raw_output_path = raw_output_path
        self.outputs: list[JsonObject] = []
        self.previous_action: AssistantAction | None = None

    @property
    def identity(self) -> PolicyIdentity:
        return self._identity

    def begin_case(self, *, case_id: str, seed: int) -> None:
        del case_id
        importlib.import_module("transformers").set_seed(seed)
        self.previous_action = None

    def act(self, context: EvaluationContext) -> AssistantAction:
        from .hf_peft import _predict

        source = evaluation_source(context, self.previous_action)
        mapped = map_source_example(source, mix=TrainingMix.JOINT_CORRECTIVE)
        assert mapped is not None
        started = time.monotonic()
        metrics: JsonObject = {}
        text = _predict(
            self.model,
            self.tokenizer,
            mapped,
            max_new_tokens=self.max_new_tokens,
            metrics=metrics,
        )
        action = parse_model_action(
            text, command_id=f"{source.example_id}:parse-failure"
        )
        self.outputs.append(
            {
                "case_id": context.case_id,
                "turn": context.turn_index,
                "raw_output": text,
                "action": action.to_dict(),
                "wall_seconds": time.monotonic() - started,
                "generation_metrics": metrics,
            }
        )
        if self.raw_output_path is not None:
            with self.raw_output_path.open(
                "a", encoding="utf-8", newline="\n"
            ) as stream:
                stream.write(canonical_json(self.outputs[-1]) + "\n")
        if len(self.outputs) % 10 == 0:
            print(
                f"{self.identity.policy_id}: evaluated {len(self.outputs)} actions",
                flush=True,
            )
        self.previous_action = action
        return action


def run_variant_worker(
    corpus: Path,
    output: Path,
    *,
    variant: str,
    git_commit: str,
    seed: int,
    gpu_hours: float,
) -> JsonObject:
    """Train/export one real variant, then run the entire frozen evaluation."""

    from .hf_peft import run_hf_peft_training

    print(f"Starting real variant {variant}", flush=True)
    binding = resolve_model_binding("primary")
    sources, dataset = load_corpus_examples(corpus)
    checkpoints = list((output / "checkpoints").glob("checkpoint-*"))
    resume = (
        max(checkpoints, key=lambda p: int(p.name.split("-")[-1]))
        if checkpoints
        else None
    )
    result_path = output / "training-result.json"
    if variant == "prompt-only":
        result: JsonObject = {"run_id": binding.native_revision}
    elif result_path.exists():
        result = cast(JsonObject, json.loads(result_path.read_text()))
        for name, digest in cast(dict[str, str], result["artifact_hashes"]).items():
            if sha256_file(output / name) != digest:
                raise CampaignError(f"completed candidate artifact changed: {name}")
    else:
        mix = TrainingMix(variant)
        config = load_training_config("primary", mix=mix, seed=seed)
        result = run_hf_peft_training(
            map_dataset(sources, mix=mix),
            binding=binding,
            config=config,
            dataset=dataset,
            budget=BudgetAuthorization(gpu_hours, 0.0, 0.0),
            output_dir=output,
            git_commit=git_commit,
            resume_from_checkpoint=str(resume) if resume else None,
        )
    adapter = HFStudentAdapter(
        binding,
        adapter_dir=None if variant == "prompt-only" else output / "adapter",
        variant=variant,
        revision=str(result["run_id"]),
        raw_output_path=output / "raw-generations.jsonl",
    )
    report = run_benchmark(adapter, code_revision=git_commit)
    write_json(output / "benchmark.json", cast(JsonObject, report.to_dict()))
    (output / "benchmark.md").write_text(report.to_markdown(), encoding="utf-8")
    metadata: JsonObject = {
        "variant": variant,
        "base_checkpoint": binding.to_object(),
        "dataset_hash": dataset.dataset_hash,
        "decoding": {"do_sample": False, "max_new_tokens": 384},
        "runtime": "hf-transformers-peft-native-float32",
        "quantization": "none",
        "training_run": result["run_id"],
        "substantive": True,
    }
    # The TTT-014 runner is a separate read-only evaluation consumer.
    closed_loop = importlib.import_module(
        "techrotic_training_triumvirate.evaluation.closedloop"
    )
    extended = closed_loop.run_closed_loop(
        adapter, code_revision=git_commit, candidate_metadata=metadata
    )
    write_json(output / "closed-loop.json", cast(JsonObject, extended.to_dict()))
    outputs: list[JsonValue] = [item for item in adapter.outputs]
    write_json(output / "outputs.json", {"outputs": outputs})
    write_json(output / "candidate-metadata.json", metadata)
    return {
        "variant": variant,
        "run_id": result["run_id"],
        "benchmark_sha256": sha256_file(output / "benchmark.json"),
        "closed_loop_sha256": sha256_file(output / "closed-loop.json"),
        "quality_evidence": True,
    }


def verify_completed_worker(root: Path, *, variant: str, git_commit: str) -> None:
    """Read back every required artifact before accepting or skipping a worker."""

    try:
        worker = json.loads((root / "worker-result.json").read_text(encoding="utf-8"))
        if (
            worker.get("variant") != variant
            or worker.get("quality_evidence") is not True
        ):
            raise CampaignError("completed worker variant/quality identity changed")
        for name, key in (
            ("benchmark.json", "benchmark_sha256"),
            ("closed-loop.json", "closed_loop_sha256"),
        ):
            if sha256_file(root / name) != worker[key]:
                raise CampaignError(f"completed worker {name} SHA-256 changed")
        benchmark = json.loads((root / "benchmark.json").read_text(encoding="utf-8"))
        extended = json.loads((root / "closed-loop.json").read_text(encoding="utf-8"))
        metadata = json.loads(
            (root / "candidate-metadata.json").read_text(encoding="utf-8")
        )
        expected_policy = f"pilot-{variant.replace('+', '-')}"
        if (
            benchmark["code_revision"] != git_commit
            or benchmark["policy"]["policy_id"] != expected_policy
            or extended["evidence"]["code_revision"] != git_commit
            or extended["evidence"]["policy"]["policy_id"] != expected_policy
            or metadata["variant"] != variant
            or metadata["base_checkpoint"]
            != resolve_model_binding("primary").to_object()
            or extended["evidence"]["candidate_metadata"] != metadata
        ):
            raise CampaignError("completed worker policy/source/model identity changed")
        verifier = importlib.import_module(
            "techrotic_training_triumvirate.evaluation.closedloop"
        )
        verifier.verify_closed_loop_report(extended)
        if variant != "prompt-only":
            trained = json.loads(
                (root / "training-result.json").read_text(encoding="utf-8")
            )
            if (
                trained["run_id"] != worker["run_id"]
                or metadata["training_run"] != trained["run_id"]
            ):
                raise CampaignError("completed worker training identity changed")
            for name, digest in trained["artifact_hashes"].items():
                artifact = (root / name).resolve()
                if (
                    not artifact.is_relative_to(root.resolve())
                    or sha256_file(artifact) != digest
                ):
                    raise CampaignError(f"completed candidate artifact changed: {name}")
            run_manifest = root / "run-manifest.json"
            if sha256_file(run_manifest) != trained["run_manifest_sha256"]:
                raise CampaignError("completed candidate run manifest changed")
            manifest = json.loads(run_manifest.read_text(encoding="utf-8"))
            if manifest["payload"]["git_commit"] != git_commit:
                raise CampaignError("completed candidate source revision changed")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, CampaignError):
            raise
        raise CampaignError(
            f"completed worker evidence missing or invalid: {exc}"
        ) from exc


def _run_pilot_campaign(
    corpus: str | Path,
    output: str | Path,
    *,
    execution_host: str,
    allocation_id: str,
    git_commit: str,
    allow_heavy: bool = False,
    gpu_hours: float = 4.0,
    seed: int = 24301,
    gpu_index: int = 0,
) -> JsonObject:
    """Execute sequential isolated workers with persisted conservative budget caps."""

    if not allow_heavy:
        raise CampaignError("real campaign requires explicit allow_heavy")
    if not execution_host.strip() or not allocation_id.strip():
        raise CampaignError("named execution host and allocation are required")
    if not math.isfinite(gpu_hours) or gpu_hours <= 0 or gpu_hours > 24:
        raise CampaignError("GPU budget must be finite, positive and at most 24 hours")
    root = Path(output).resolve()
    corpus_root = Path(corpus).resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan = build_pilot_plan(
        corpus_root,
        seed=seed,
        gpu_hours=gpu_hours,
        external_compute_cost_gbp=0.0,
        execution_host=execution_host,
        allocation_id=allocation_id,
    )
    identity = content_hash(
        {"plan": plan, "git_commit": git_commit, "gpu_index": gpu_index}
    )
    state_path = root / "campaign.json"
    state: JsonObject = {
        "schema": "ttt.pilot_campaign",
        "schema_version": 1,
        "campaign_identity": identity,
        "plan": plan,
        "host": collect_host(),
        "git_commit": git_commit,
        "charged_gpu_hours": 0.0,
        "external_compute_cost_gbp": 0.0,
        "paid_model_api_cost_gbp": 0.0,
        "variants": {},
        "status": "running",
        "substantive_campaign_executed": False,
    }
    if state_path.exists():
        state = cast(JsonObject, json.loads(state_path.read_text()))
        if state.get("campaign_identity") != identity:
            raise CampaignError(
                "resume campaign model/data/profile/allocation identity changed"
            )
    variants = cast(JsonObject, state["variants"])
    candidate_variants = ("prompt-only", *(mix.value for mix in PILOT_MIXES))
    for variant in candidate_variants:
        slug = variant.replace("+", "-")
        existing = variants.get(variant)
        if isinstance(existing, dict) and existing.get("status") == "complete":
            verify_completed_worker(root / slug, variant=variant, git_commit=git_commit)
            continue
        per_variant = gpu_hours / len(candidate_variants)
        charged = float(cast(float, state["charged_gpu_hours"]))
        if charged + per_variant > gpu_hours + 1e-9:
            state["status"] = "budget_exhausted"
            break
        # Charge the full cap before launching: interruption cannot reset budget.
        state["charged_gpu_hours"] = charged + per_variant
        variants[variant] = {"status": "running", "reserved_gpu_hours": per_variant}
        write_json(state_path, state)
        variant_root = root / slug
        variant_root.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "techrotic_training_triumvirate.training.campaign",
            "--worker",
            "--corpus",
            str(corpus_root),
            "--output",
            str(variant_root),
            "--variant",
            variant,
            "--git-commit",
            git_commit,
            "--seed",
            str(seed),
            "--gpu-hours",
            str(per_variant),
        ]
        environment = dict(os.environ)
        environment["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
        environment["PYTHONUNBUFFERED"] = "1"
        started = time.monotonic()
        status = "failed"
        error: str | None = None
        returncode: int | None = None
        with (variant_root / "worker.log").open("a", encoding="utf-8") as log:
            try:
                child = subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=environment,
                    timeout=per_variant * 3600,
                    check=False,
                )
                returncode = child.returncode
                status = "complete" if returncode == 0 else "failed"
                if status == "complete":
                    try:
                        verify_completed_worker(
                            variant_root, variant=variant, git_commit=git_commit
                        )
                    except CampaignError as exc:
                        status = "failed"
                        error = str(exc)
            except subprocess.TimeoutExpired:
                status = "hard_budget_stop"
                error = "worker exceeded the reserved single-GPU wall-time cap"
        elapsed = time.monotonic() - started
        # Reconcile successful process accounting; unknown interrupted reservations
        # deliberately remain fully charged on restart.
        state["charged_gpu_hours"] = charged + min(per_variant, elapsed / 3600)
        variants[variant] = {
            "status": status,
            "returncode": returncode,
            "error": error,
            "wall_seconds": elapsed,
            "charged_gpu_hours": min(per_variant, elapsed / 3600),
            "worker_log_sha256": sha256_file(variant_root / "worker.log"),
        }
        state["substantive_campaign_executed"] = any(
            (root / item.value.replace("+", "-") / "training-result.json").is_file()
            for item in PILOT_MIXES
        )
        write_json(state_path, state)
    if all(
        isinstance(v, dict) and v.get("status") == "complete" for v in variants.values()
    ) and len(variants) == len(candidate_variants):
        state["status"] = "complete"
    elif state["status"] != "budget_exhausted":
        state["status"] = "incomplete"
    write_json(state_path, state)
    return state


def run_pilot_campaign(
    corpus: str | Path,
    output: str | Path,
    *,
    execution_host: str,
    allocation_id: str,
    git_commit: str,
    allow_heavy: bool = False,
    gpu_hours: float = 4.0,
    seed: int = 24301,
    gpu_index: int = 0,
) -> JsonObject:
    """Serialize admission/accounting so concurrent invocations cannot overspend."""

    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "campaign.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise CampaignError(
            "campaign lock exists; verify its process stopped before removing it"
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        return _run_pilot_campaign(
            corpus,
            root,
            execution_host=execution_host,
            allocation_id=allocation_id,
            git_commit=git_commit,
            allow_heavy=allow_heavy,
            gpu_hours=gpu_hours,
            seed=seed,
            gpu_index=gpu_index,
        )
    finally:
        lock.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Private worker entry point; public commands use the campaign script."""

    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--variant",
        choices=["prompt-only", *(m.value for m in PILOT_MIXES)],
        required=True,
    )
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--seed", type=int, default=24301)
    parser.add_argument("--gpu-hours", type=float, required=True)
    args = parser.parse_args(argv)
    if not math.isfinite(args.gpu_hours) or not 0 < args.gpu_hours <= 6:
        parser.error("worker GPU-hours must be positive, finite and at most six")
    # The worker owns its hard deadline even if its supervising process exits.
    watchdog = threading.Timer(args.gpu_hours * 3600, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    try:
        result = run_variant_worker(
            args.corpus,
            args.output,
            variant=args.variant,
            git_commit=args.git_commit,
            seed=args.seed,
            gpu_hours=args.gpu_hours,
        )
        write_json(args.output / "worker-result.json", result)
        return 0
    except Exception as exc:
        write_json(
            args.output / "worker-failure.json",
            {"error_type": type(exc).__name__, "error": str(exc)},
        )
        raise
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
