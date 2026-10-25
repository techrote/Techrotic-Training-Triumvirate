"""Worker host hard-deadline, cancellation and ownership tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from techrotic_training_triumvirate.experiments.worker import (
    WorkerHostError,
    WorkerOwnership,
    WorkerSpec,
    process_creation_token,
    request_cancel,
    run_host,
    write_spec,
)


def _spec(tmp_path: Path, *, code: str, deadline: float = 5.0) -> WorkerSpec:
    return WorkerSpec(
        attempt_id="attempt-1",
        argv=(sys.executable, "-c", code),
        cwd=str(tmp_path),
        environment={},
        deadline_seconds=deadline,
        artifact_root=str(tmp_path),
        source_hash="a" * 64,
        config_hash="b" * 64,
        launch_nonce="nonce-1",
    )


def test_worker_host_records_successful_fixed_argv_completion(tmp_path: Path) -> None:
    path = tmp_path / "spec.json"
    write_spec(path, _spec(tmp_path, code="print('worker-ok')"))
    assert run_host(path) == 0
    completion = json.loads(
        (tmp_path / "attempt-1/host-complete.json").read_text(encoding="utf-8")
    )
    assert completion["reason"] == "exited"
    assert completion["returncode"] == 0
    assert "worker-ok" in (tmp_path / "attempt-1/worker.log").read_text()


def test_windows_termination_refuses_missing_job_before_posix_signal(
    monkeypatch,
) -> None:
    from techrotic_training_triumvirate.experiments import worker

    monkeypatch.setattr(worker.sys, "platform", "win32")
    process = SimpleNamespace(poll=lambda: None)
    with pytest.raises(WorkerHostError, match="owned Job Object"):
        worker._terminate_process_tree(process, None, grace_seconds=0.1)


def test_worker_host_enforces_deadline_without_controller_polling(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spec.json"
    write_spec(
        path,
        _spec(
            tmp_path,
            code="import time; time.sleep(30)",
            deadline=0.1,
        ),
    )
    assert run_host(path) == 124
    completion = json.loads(
        (tmp_path / "attempt-1/host-complete.json").read_text(encoding="utf-8")
    )
    assert completion["reason"] == "deadline"


def test_preexisting_cancel_request_stops_only_the_owned_worker_tree(
    tmp_path: Path,
) -> None:
    path = tmp_path / "spec.json"
    write_spec(
        path,
        _spec(tmp_path, code="import time; time.sleep(30)", deadline=10),
    )
    cancel = tmp_path / "attempt-1/cancel-request.json"
    cancel.parent.mkdir()
    cancel.write_text('{"reason":"test"}\n', encoding="utf-8")
    assert run_host(path) == 124
    completion = json.loads(
        (tmp_path / "attempt-1/host-complete.json").read_text(encoding="utf-8")
    )
    assert completion["reason"] == "cancelled"


@pytest.mark.skipif(os.name == "nt", reason="uses /proc creation token semantics")
def test_pid_reuse_guard_rejects_changed_creation_token(tmp_path: Path) -> None:
    token = process_creation_token(os.getpid())
    ownership = WorkerOwnership(
        pid=os.getpid(),
        creation_token=token + "-forged",
        launch_nonce="nonce",
        source_hash="a" * 64,
        config_hash="b" * 64,
        spec_hash="c" * 64,
    )
    with pytest.raises(WorkerHostError, match="reused|ownership"):
        request_cancel(ownership, tmp_path / "cancel.json", reason="test")
