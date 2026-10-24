"""CPU-only, parent-verified trained commander merge and Q4 export."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from techrotic_training_triumvirate.training.admission import (
    load_training_config,
    resolve_model_binding,
)
from techrotic_training_triumvirate.training.campaign import write_json
from techrotic_training_triumvirate.training.campaign_integrity import (
    verify_training_reuse,
)
from techrotic_training_triumvirate.training.data import load_corpus_examples
from techrotic_training_triumvirate.training.export import sha256_file
from techrotic_training_triumvirate.training.model import TrainingMix

UPSTREAM = "2afcdb9777b1bac79fa4bfe284b9bf23085b0469"
BINARY_ZIP_SHA = "da31e42afd92d0730c81b59136f92a2c6d10c0bc114b293c6c36f59125133556"
CUDA_ZIP_SHA = "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"


def verify_binary_archive(
    archive: Path, expected: str, binaries: Path
) -> dict[str, str]:
    """Check extracted executables/DLLs against the upstream digest-bound archive."""
    if sha256_file(archive) != expected:
        raise ValueError("upstream binary archive digest mismatch")
    inventory = {}
    with zipfile.ZipFile(archive) as package:
        for name in package.namelist():
            if Path(name).suffix.lower() not in {".exe", ".dll"}:
                continue
            path = binaries / Path(name).name
            digest = hashlib.sha256(package.read(name)).hexdigest()
            if not path.is_file() or sha256_file(path) != digest:
                raise ValueError("extracted tool differs from upstream archive")
            inventory[path.name] = digest
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--semantic-source", required=True)
    parser.add_argument("--driver-source", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh derivative directory required")
    if not (args.training / "worker-complete.json").is_file():
        raise ValueError("interim/incomplete checkpoints cannot be qualified")
    binding = resolve_model_binding("primary")
    config = load_training_config(
        "primary", profile_version=2, mix=TrainingMix.JOINT_CORRECTIVE, seed=24302
    )
    _, dataset = load_corpus_examples(args.corpus)
    result = verify_training_reuse(
        args.training,
        binding=binding,
        config=config,
        dataset=dataset,
        source_revision=args.semantic_source,
    ).result
    source = args.tools / "llama-source"
    actual = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual != UPSTREAM:
        raise ValueError("converter source revision mismatch")
    converter = source / "convert_hf_to_gguf.py"
    committed = subprocess.run(
        ["git", "-C", str(source), "show", "HEAD:convert_hf_to_gguf.py"],
        check=True,
        capture_output=True,
    ).stdout
    if converter.read_bytes().replace(b"\r\n", b"\n") != committed.replace(
        b"\r\n", b"\n"
    ):
        raise ValueError("converter source is modified")
    binary = args.tools / "llama-win"
    inventory = verify_binary_archive(
        args.tools / "llama-b8185-bin-win-cuda-12.4-x64.zip", BINARY_ZIP_SHA, binary
    )
    inventory.update(
        verify_binary_archive(
            args.tools / "cudart-llama-bin-win-cuda-12.4-x64.zip", CUDA_ZIP_SHA, binary
        )
    )
    args.output.mkdir(parents=True)
    environment = {**os.environ, "CUDA_VISIBLE_DEVICES": ""}
    started = time.monotonic()
    merged = args.output / "merged"
    f16 = args.output / "commander-f16.gguf"
    q4 = args.output / "commander-Q4_K_M.gguf"
    commands = [
        [
            sys.executable,
            str(Path(__file__).with_name("merge_commander.py")),
            "--adapter",
            str(args.training / "adapter"),
            "--output",
            str(merged),
        ],
        [
            sys.executable,
            str(converter),
            str(merged),
            "--outfile",
            str(f16),
            "--outtype",
            "f16",
        ],
        [str(binary / "llama-quantize.exe"), str(f16), str(q4), "Q4_K_M", "4"],
    ]
    for index, command in enumerate(commands):
        with (args.output / f"stage-{index}.log").open(
            "w", encoding="utf-8", newline="\n"
        ) as log:
            subprocess.run(
                command,
                check=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=environment,
                timeout=1200,
            )
    sys.path.insert(0, str(source / "gguf-py"))
    from gguf import GGUFReader, LlamaFileType

    metadata = GGUFReader(q4)
    file_type = metadata.fields["general.file_type"].contents()
    if file_type != int(LlamaFileType.MOSTLY_Q4_K_M):
        raise ValueError("actual GGUF metadata is not Q4_K_M")
    write_json(
        args.output / "export-manifest.json",
        {
            "schema": "ttt.q4_commander_export",
            "schema_version": 1,
            "quantization": "Q4_K_M",
            "gguf_file_type": file_type,
            "training_run": result["run_id"],
            "semantic_source": args.semantic_source,
            "training_manifest_sha256": sha256_file(
                args.training / "run-manifest.json"
            ),
            "adapter_sha256": sha256_file(
                args.training / "adapter/adapter_model.safetensors"
            ),
            "merged_manifest_sha256": sha256_file(merged / "merge-manifest.json"),
            "f16_sha256": sha256_file(f16),
            "q4_sha256": sha256_file(q4),
            "q4_size_bytes": q4.stat().st_size,
            "device": "cpu",
            "wall_seconds": time.monotonic() - started,
            "driver_source_revision": args.driver_source,
            "driver_sha256": sha256_file(Path(__file__)),
            "converter_source_revision": UPSTREAM,
            "converter_sha256": sha256_file(converter),
            "binary_archive_sha256": BINARY_ZIP_SHA,
            "cuda_archive_sha256": CUDA_ZIP_SHA,
            "runtime_files": inventory,
            "commands": commands,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
