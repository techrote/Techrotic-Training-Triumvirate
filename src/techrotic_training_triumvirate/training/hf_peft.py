"""Opt-in Hugging Face Transformers + PEFT LoRA execution backend.

The module deliberately imports heavyweight dependencies only inside the execution
function. Default CI exercises mapping, masking, checkpoint/resume, export, and parity
through the stdlib tiny backend without downloading a model.
"""

from __future__ import annotations

import gc
import importlib
import os
import time
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.schemas import JsonObject, JsonValue, canonical_json

from .campaign_integrity import expected_training_identity, verify_checkpoint_identity
from .device_admission import verify_cuda_environment
from .export import build_run_manifest, sha256_file
from .model import (
    BudgetAuthorization,
    DatasetIdentity,
    MappedExample,
    ModelBinding,
    TrainingConfig,
)


class HFTrainingError(RuntimeError):
    """Raised when the optional HF/PEFT backend cannot execute safely."""


def _messages(example: MappedExample) -> list[dict[str, str]]:
    return [
        {"role": item.role, "content": item.content} for item in example.prompt_messages
    ]


def tokenize_for_causal_lm(
    tokenizer: Any,
    example: MappedExample,
    *,
    max_sequence_tokens: int,
) -> dict[str, list[int]]:
    """Render the native chat template and mask all non-assistant target tokens."""

    prompt_messages = _messages(example)
    full_messages = [
        *prompt_messages,
        {"role": "assistant", "content": example.assistant_target},
    ]
    prompt_ids = cast(
        list[int],
        tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=True,
            add_generation_prompt=True,
        ),
    )
    full_ids = cast(
        list[int],
        tokenizer.apply_chat_template(
            full_messages,
            tokenize=True,
            add_generation_prompt=False,
        ),
    )
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise HFTrainingError(
            "native chat template does not preserve the generation-prefix boundary"
        )
    if len(full_ids) > max_sequence_tokens:
        raise HFTrainingError(
            f"mapped example {example.example_id} exceeds max_sequence_tokens"
        )
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
    if not any(label != -100 for label in labels):
        raise HFTrainingError("assistant target produced no trainable tokens")
    return {
        "input_ids": full_ids,
        "attention_mask": [1] * len(full_ids),
        "labels": labels,
    }


def _predict(
    model: Any,
    tokenizer: Any,
    example: MappedExample,
    *,
    max_new_tokens: int,
    metrics: JsonObject | None = None,
) -> str:
    prompt = _messages(example)
    encoded = tokenizer.apply_chat_template(
        prompt,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    encoded = encoded.to(model.device)
    started = time.monotonic()
    output = model.generate(
        encoded,
        attention_mask=encoded.new_ones(encoded.shape),
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    generated = output[0][encoded.shape[-1] :]
    text = str(tokenizer.decode(generated, skip_special_tokens=True))
    elapsed = time.monotonic() - started
    if metrics is not None:
        count = int(generated.shape[-1])
        metrics.update(
            generated_tokens=count,
            generation_seconds=elapsed,
            tokens_per_second=count / elapsed if elapsed else 0.0,
        )
    return text


def verify_native_checkpoint(binding: ModelBinding) -> JsonObject:
    """Download the admitted native weights and verify their recorded digest."""

    hub = importlib.import_module("huggingface_hub")
    hashes: JsonObject = {}
    for name in binding.native_artifact_names:
        path = hub.hf_hub_download(
            binding.native_repository, name, revision=binding.native_revision
        )
        digest = sha256_file(Path(path))
        hashes[name] = digest
        if (
            binding.native_artifact_sha256 is not None
            and digest != binding.native_artifact_sha256
        ):
            raise HFTrainingError(
                f"admitted native checkpoint SHA-256 mismatch: {name}"
            )
    return hashes


def run_hf_peft_training(
    mapped: tuple[MappedExample, ...],
    *,
    binding: ModelBinding,
    config: TrainingConfig,
    dataset: DatasetIdentity,
    budget: BudgetAuthorization,
    output_dir: str | Path,
    git_commit: str,
    resume_from_checkpoint: str | None = None,
) -> JsonObject:
    """Run admitted LoRA SFT and verify adapter save/reload inference parity."""

    if config.backend != "hf-transformers-peft" or config.method != "lora":
        raise HFTrainingError("only the admitted hf-transformers-peft LoRA path exists")
    train_examples = tuple(item for item in mapped if item.split == "train")
    if not train_examples:
        raise HFTrainingError("no training-split examples are available")

    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    identity_record = expected_training_identity(
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=git_commit,
    )
    training_identity = str(identity_record["training_identity"])
    identity_path = root / "training-identity.json"
    if identity_path.exists():
        verify_checkpoint_identity(
            root,
            binding=binding,
            config=config,
            dataset=dataset,
            source_revision=git_commit,
        )
    elif resume_from_checkpoint is not None:
        raise HFTrainingError(
            "resume requires the TTT training-identity.json from the original run"
        )
    else:
        identity_path.write_text(
            f"{canonical_json(identity_record)}\n",
            encoding="utf-8",
            newline="\n",
        )

    if resume_from_checkpoint is not None:
        checkpoint = Path(resume_from_checkpoint).resolve()
        if not checkpoint.is_relative_to(root / "checkpoints"):
            raise HFTrainingError("resume checkpoint must belong to this run")
        if not (checkpoint / "trainer_state.json").is_file():
            raise HFTrainingError("resume checkpoint has no Trainer state")

    try:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
        peft = importlib.import_module("peft")
    except ImportError as exc:
        raise HFTrainingError(
            'install the optional training dependencies with ".[training]"'
        ) from exc

    transformers.set_seed(config.seed)
    torch.manual_seed(config.seed)
    if not torch.cuda.is_available():
        raise HFTrainingError("native heavy execution requires an admitted CUDA host")
    if torch.cuda.device_count() != 1:
        raise HFTrainingError("select exactly one CUDA GPU before heavy execution")
    gpu_identity = verify_cuda_environment(cuda=torch.cuda, environment=os.environ)
    native_hashes = verify_native_checkpoint(binding)
    started = time.monotonic()
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        binding.native_repository,
        revision=binding.native_revision,
    )
    if tokenizer.pad_token_id is None:
        if tokenizer.eos_token_id is None:
            raise HFTrainingError("tokenizer has neither pad nor eos token")
        tokenizer.pad_token = tokenizer.eos_token

    rows = [
        tokenize_for_causal_lm(
            tokenizer,
            item,
            max_sequence_tokens=config.max_sequence_tokens,
        )
        for item in train_examples
    ]

    class _Dataset:
        def __len__(self) -> int:
            return len(rows)

        def __getitem__(self, index: int) -> dict[str, list[int]]:
            return rows[index]

    pad_id = int(tokenizer.pad_token_id)

    def collate(batch: list[dict[str, list[int]]]) -> dict[str, Any]:
        maximum = max(len(item["input_ids"]) for item in batch)
        input_ids = torch.full(
            (len(batch), maximum),
            pad_id,
            dtype=torch.long,
        )
        attention_mask = torch.zeros((len(batch), maximum), dtype=torch.long)
        labels = torch.full((len(batch), maximum), -100, dtype=torch.long)
        for row_index, row in enumerate(batch):
            length = len(row["input_ids"])
            input_ids[row_index, :length] = torch.tensor(
                row["input_ids"], dtype=torch.long
            )
            attention_mask[row_index, :length] = torch.tensor(
                row["attention_mask"], dtype=torch.long
            )
            labels[row_index, :length] = torch.tensor(row["labels"], dtype=torch.long)
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    model = transformers.AutoModelForCausalLM.from_pretrained(
        binding.native_repository,
        revision=binding.native_revision,
        torch_dtype=torch.float32,
        attn_implementation="eager",
    )
    model.config.use_cache = False
    lora_config = peft.LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=(
            "all-linear"
            if config.lora_target_modules == ("all-linear",)
            else list(config.lora_target_modules)
        ),
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = peft.get_peft_model(model, lora_config)

    trainer_dir = root / "checkpoints"
    adapter_dir = root / "adapter"
    trainer_dir.mkdir(parents=True, exist_ok=True)
    arguments = transformers.TrainingArguments(
        output_dir=str(trainer_dir),
        seed=config.seed,
        data_seed=config.seed,
        num_train_epochs=config.epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.micro_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        save_strategy="steps",
        save_steps=config.save_steps,
        report_to=[],
        remove_unused_columns=False,
        fp16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        dataloader_num_workers=0,
        logging_steps=1,
        save_total_limit=2,
    )
    trainer = transformers.Trainer(
        model=model,
        args=arguments,
        train_dataset=_Dataset(),
        data_collator=collate,
    )
    train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    training_metrics = dict(train_result.metrics)
    completed_steps = int(trainer.state.global_step)
    trainer.save_state()

    parity_examples = tuple(item for item in mapped if item.split == "dev")[:3]
    if not parity_examples:
        parity_examples = train_examples[:1]
    model.config.use_cache = True
    model.eval()
    before = [
        _predict(
            model,
            tokenizer,
            item,
            max_new_tokens=config.parity_max_new_tokens,
        )
        for item in parity_examples
    ]

    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)

    del trainer
    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    reloaded_base = transformers.AutoModelForCausalLM.from_pretrained(
        binding.native_repository,
        revision=binding.native_revision,
        torch_dtype=torch.float32,
        attn_implementation="eager",
    )
    reloaded = peft.PeftModel.from_pretrained(reloaded_base, adapter_dir)
    reloaded.to("cuda")
    reloaded.eval()
    after = [
        _predict(
            reloaded,
            tokenizer,
            item,
            max_new_tokens=config.parity_max_new_tokens,
        )
        for item in parity_examples
    ]
    parity_cases: list[JsonObject] = []
    for example, pre, post in zip(parity_examples, before, after, strict=True):
        parity_cases.append(
            {
                "example_id": example.example_id,
                "equal": pre == post,
                "pre_export": pre,
                "post_export": post,
            }
        )
    if not all(bool(item["equal"]) for item in parity_cases):
        raise HFTrainingError("saved/reloaded PEFT adapter failed inference parity")

    parity_values: list[JsonValue] = [case for case in parity_cases]
    parity: JsonObject = {
        "schema_version": 1,
        "passed": True,
        "cases": parity_values,
    }
    parity_path = root / "parity.json"
    parity_path.write_text(
        f"{canonical_json(parity)}\n",
        encoding="utf-8",
        newline="\n",
    )

    artifact_hashes: JsonObject = {
        "parity.json": sha256_file(parity_path),
        "training-identity.json": sha256_file(identity_path),
    }
    for path in sorted(adapter_dir.rglob("*")):
        if path.is_file():
            artifact_hashes[path.relative_to(root).as_posix()] = sha256_file(path)

    manifest = build_run_manifest(
        phase="train-export",
        binding=binding,
        config=config,
        dataset=dataset,
        git_commit=git_commit,
        artifact_hashes=artifact_hashes,
        backend=config.backend,
        budget=budget,
        command_line=(
            "ttt-train",
            "train-hf",
            "--model",
            binding.model_key,
            "--mix",
            config.mix.value,
            "--seed",
            str(config.seed),
        ),
        extra_runtime={
            "resume_from_checkpoint": resume_from_checkpoint,
            "training_identity": training_identity,
            "parity_passed": True,
            "native_artifact_hashes": native_hashes,
            "torch_version": str(torch.__version__),
            "transformers_version": str(transformers.__version__),
            "peft_version": str(peft.__version__),
            "cuda_version": str(torch.version.cuda),
            "gpu": str(torch.cuda.get_device_name(0)),
            "gpu_identity": gpu_identity,
            "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated(0)),
            "wall_seconds": time.monotonic() - started,
        },
    )
    run_manifest_path = root / "run-manifest.json"
    run_manifest_path.write_text(
        f"{manifest.to_json()}\n",
        encoding="utf-8",
        newline="\n",
    )
    result: JsonObject = {
        "run_id": manifest.run_id,
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "adapter_dir": str(adapter_dir),
        "parity": parity,
        "artifact_hashes": artifact_hashes,
        "training_metrics": cast(JsonObject, training_metrics),
        "completed_steps": completed_steps,
        "train_examples": len(train_examples),
        "wall_seconds": time.monotonic() - started,
    }
    (root / "training-result.json").write_text(
        f"{canonical_json(result)}\n",
        encoding="utf-8",
        newline="\n",
    )
    return result
