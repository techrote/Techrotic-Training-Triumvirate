"""Opt-in Hugging Face Transformers + PEFT LoRA execution backend.

The module deliberately imports heavyweight dependencies only inside the execution
function. Default CI exercises mapping, masking, checkpoint/resume, export, and parity
through the stdlib tiny backend without downloading a model.
"""

from __future__ import annotations

import gc
import importlib
import json
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.schemas import JsonObject, canonical_json

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
        {"role": item.role, "content": item.content}
        for item in example.prompt_messages
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
) -> str:
    prompt = _messages(example)
    encoded = tokenizer.apply_chat_template(
        prompt,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    encoded = encoded.to(model.device)
    output = model.generate(
        encoded,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    generated = output[0][encoded.shape[-1] :]
    return str(tokenizer.decode(generated, skip_special_tokens=False))


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
            labels[row_index, :length] = torch.tensor(
                row["labels"], dtype=torch.long
            )
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    model = transformers.AutoModelForCausalLM.from_pretrained(
        binding.native_repository,
        revision=binding.native_revision,
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

    root = Path(output_dir)
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
    )
    trainer = transformers.Trainer(
        model=model,
        args=arguments,
        train_dataset=_Dataset(),
        data_collator=collate,
    )
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    parity_examples = tuple(item for item in mapped if item.split == "dev")[:3]
    if not parity_examples:
        parity_examples = train_examples[:1]
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
    )
    reloaded = peft.PeftModel.from_pretrained(reloaded_base, adapter_dir)
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

    parity: JsonObject = {
        "schema_version": 1,
        "passed": True,
        "cases": parity_cases,
    }
    parity_path = root / "parity.json"
    parity_path.write_text(
        f"{canonical_json(parity)}\n",
        encoding="utf-8",
        newline="\n",
    )

    artifact_hashes: JsonObject = {"parity.json": sha256_file(parity_path)}
    for path in sorted(adapter_dir.rglob("*")):
        if path.is_file():
            artifact_hashes[str(path.relative_to(root))] = sha256_file(path)

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
            "parity_passed": True,
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
    }
    (root / "training-result.json").write_text(
        f"{canonical_json(result)}\n",
        encoding="utf-8",
        newline="\n",
    )
    return result
