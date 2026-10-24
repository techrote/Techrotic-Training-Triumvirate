"""Export refuses incomplete training and altered upstream executable bytes."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

from techrotic_training_triumvirate.training.export import sha256_file


def exporter():
    path = Path(__file__).resolve().parents[1] / "scripts/export_commander.py"
    spec = importlib.util.spec_from_file_location("commander_export_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extracted_binary_is_verified_against_the_digest_bound_archive(
    tmp_path: Path,
) -> None:
    module = exporter()
    archive = tmp_path / "upstream.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("llama-server.exe", b"synthetic binary fixture")
    binary = tmp_path / "llama-server.exe"
    binary.write_bytes(b"synthetic binary fixture")
    assert module.verify_binary_archive(archive, sha256_file(archive), tmp_path)[
        "llama-server.exe"
    ] == sha256_file(binary)
    binary.write_bytes(b"changed after extraction")
    with pytest.raises(ValueError, match="differs from upstream"):
        module.verify_binary_archive(archive, sha256_file(archive), tmp_path)


def test_interim_checkpoint_cannot_enter_qualification_export(
    tmp_path: Path, monkeypatch
) -> None:
    module = exporter()
    training = tmp_path / "unfinished"
    training.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "export_commander",
            "--training",
            str(training),
            "--corpus",
            str(tmp_path / "corpus"),
            "--output",
            str(tmp_path / "out"),
            "--tools",
            str(tmp_path / "tools"),
            "--semantic-source",
            "a" * 40,
            "--driver-source",
            "b" * 40,
        ],
    )
    with pytest.raises(ValueError, match="interim/incomplete"):
        module.main()
