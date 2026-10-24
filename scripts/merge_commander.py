"""CPU-only PEFT merge with pinned base/adapter provenance for GGUF conversion."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Conversion must never initialize either GPU.
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from techrotic_training_triumvirate.training.admission import resolve_model_binding
from techrotic_training_triumvirate.training.campaign import write_json
from techrotic_training_triumvirate.training.export import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose fresh derivative output; never overwrite evidence")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from techrotic_training_triumvirate.training.hf_peft import verify_native_checkpoint

    torch.set_num_threads(4)
    binding = resolve_model_binding("primary")
    base_hashes = verify_native_checkpoint(binding)
    config = json.loads((args.adapter / "adapter_config.json").read_text())
    if config["base_model_name_or_path"] != binding.native_repository:
        raise ValueError("adapter base differs from admission")
    source_hashes = {
        p.name: sha256_file(p) for p in args.adapter.iterdir() if p.is_file()
    }
    base = AutoModelForCausalLM.from_pretrained(
        binding.native_repository,
        revision=binding.native_revision,
        torch_dtype=torch.float32,
        device_map="cpu",
        attn_implementation="eager",
    )
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload(
        safe_merge=True
    )
    merged.to(torch.float16)
    merged.save_pretrained(args.output, safe_serialization=True)
    tokenizer = AutoTokenizer.from_pretrained(
        binding.native_repository, revision=binding.native_revision
    )
    tokenizer.save_pretrained(args.output)
    write_json(
        args.output / "merge-manifest.json",
        {
            "schema": "ttt.merged_commander",
            "schema_version": 1,
            "base_checkpoint": binding.to_object(),
            "verified_native_files": base_hashes,
            "adapter_files": source_hashes,
            "merge_dtype": "float32",
            "stored_dtype": "float16",
            "device": "cpu",
            "cuda_visible_devices": "",
            "merged_files": {
                p.name: sha256_file(p) for p in args.output.iterdir() if p.is_file()
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
