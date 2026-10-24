"""Worker containment, deadlines, ownership, and cancellation identity tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from techrotic_training_triumvirate.experiments import (
    OwnedProcess,
    WorkerContainmentError,
    WorkerSpec,
    process_creation_token,
    request_cancel,
    run_worker_host,
    verify_owned_process,
    write_worker_spec,
)
from techrotic_training_triumvirate.experiments.worker import load_worker_spec


def _spec(tmp_path: Path, code: str, *, deadline: int = 5) -> WorkerSpec:
    return WorkerSpec(
        attempt_id="a" * 64,
        launch_nonce="worker-fixture",
        source_sha256="b" * 64,
        config_sha256="c" * 64,
        argv=(sys.executable, "-c", code),
        cwd=str(tmp_path),
        environment=dict(os.environ),
        deadline_seconds=deadline,
        grace_seconds=1,
        ownership_path=str(tmp_path / "owned.json"),
        stop_path=str(tmp_path / "stop.json"),
        result_path=str(tmp_path / "result.json"),
        log_path=str(tmp_path / "worker.log"),
    )


def test_worker_host_records_os_owned_identity_and_success(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "print('worker-ok')")
    result = run_worker_host(spec)
    assert result["completed_successfully"] is True
    assert result["timed_out"] is False
    assert result["cancelled"] is False
    owned = OwnedProcess.from_object(
        json.loads((tmp_path / "owned.json").read_text())
    )
    assert owned.attempt_id == spec.attempt_id
    assert (tmp_path / "worker.log").read_text().strip() == "worker-ok"


def test_worker_host_enforces_deadline_without_controller_polling(
    tmp_path: Path,
) -> None:
    spec = _spec(tmp_path, "import time; time.sleep(30)", deadline=1)
    result = run_worker_host(spec)
    assert result["completed_successfully"] is False
    assert result["timed_out"] is True
    assert result["cancelled"] is False


def test_pid_reuse_identity_mismatch_refuses_cancellation(tmp_path: Path) -> None:
    token = process_creation_token(os.getpid())
    if token is None:
        pytest.skip("platform does not expose a process creation identity")
    spec = _spec(tmp_path, "print('unused')")
    fake = OwnedProcess(
        pid=os.getpid(),
        creation_token=token + "-reused",
        attempt_id=spec.attempt_id,
        launch_nonce=spec.launch_nonce,
        source_sha256=spec.source_sha256,
        config_sha256=spec.config_sha256,
        job_name=spec.job_name,
    )
    (tmp_path / "owned.json").write_text(
        json.dumps(fake.to_object()),
        encoding="utf-8",
    )
    assert verify_owned_process(fake) is False
    with pytest.raises(WorkerContainmentError, match="PID was reused"):
        request_cancel(spec)
    assert not (tmp_path / "stop.json").exists()


def test_worker_spec_round_trip_is_argv_based_not_shell_text(tmp_path: Path) -> None:
    spec = _spec(tmp_path, "print('safe')")
    path = tmp_path / "spec.json"
    write_worker_spec(path, spec)
    loaded = load_worker_spec(path)
    assert loaded == spec
    assert loaded.argv[0] == sys.executable
    assert isinstance(loaded.argv, tuple)
