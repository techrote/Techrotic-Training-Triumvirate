"""Detached bounded worker host with owned-process cancellation and containment."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from techrotic_training_triumvirate.schemas import (
    JsonObject,
    JsonValue,
    canonical_json,
    content_hash,
)


class WorkerHostError(ValueError):
    """Worker launch, ownership, cancellation, or containment failed closed."""


def _sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise WorkerHostError(f"{field} must be a lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    attempt_id: str
    argv: tuple[str, ...]
    cwd: str
    environment: dict[str, str]
    deadline_seconds: float
    artifact_root: str
    source_hash: str
    config_hash: str
    launch_nonce: str
    grace_seconds: float = 5.0

    @classmethod
    def from_object(cls, value: object) -> WorkerSpec:
        if not isinstance(value, dict):
            raise WorkerHostError("worker spec must be an object")
        required = {
            "attempt_id",
            "argv",
            "cwd",
            "environment",
            "deadline_seconds",
            "artifact_root",
            "source_hash",
            "config_hash",
            "launch_nonce",
        }
        optional = {"grace_seconds"}
        if not required.issubset(value) or set(value) - required - optional:
            raise WorkerHostError("worker spec has invalid fields")
        raw_argv = value["argv"]
        if (
            not isinstance(raw_argv, list)
            or not raw_argv
            or not all(isinstance(item, str) and item for item in raw_argv)
        ):
            raise WorkerHostError("worker argv must contain non-empty strings")
        raw_environment = value["environment"]
        if not isinstance(raw_environment, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in raw_environment.items()
        ):
            raise WorkerHostError("worker environment must contain strings")
        deadline = value["deadline_seconds"]
        if (
            isinstance(deadline, bool)
            or not isinstance(deadline, (int, float))
            or not 0 < float(deadline) <= 86400
        ):
            raise WorkerHostError("worker deadline must be in (0, 86400]")
        grace = value.get("grace_seconds", 5.0)
        if (
            isinstance(grace, bool)
            or not isinstance(grace, (int, float))
            or not 0 < float(grace) <= 60
        ):
            raise WorkerHostError("worker grace period must be in (0, 60]")
        fields = {
            name: value[name]
            for name in ("attempt_id", "cwd", "artifact_root", "launch_nonce")
        }
        if any(not isinstance(item, str) or not item for item in fields.values()):
            raise WorkerHostError(
                "worker identity/path fields must be non-empty strings"
            )
        return cls(
            attempt_id=cast(str, value["attempt_id"]),
            argv=tuple(cast(list[str], raw_argv)),
            cwd=cast(str, value["cwd"]),
            environment=dict(cast(dict[str, str], raw_environment)),
            deadline_seconds=float(deadline),
            artifact_root=cast(str, value["artifact_root"]),
            source_hash=_sha256(value["source_hash"], "source_hash"),
            config_hash=_sha256(value["config_hash"], "config_hash"),
            launch_nonce=cast(str, value["launch_nonce"]),
            grace_seconds=float(grace),
        )

    def to_object(self) -> JsonObject:
        argv: list[JsonValue] = list(self.argv)
        return {
            "attempt_id": self.attempt_id,
            "argv": argv,
            "cwd": self.cwd,
            "environment": dict(self.environment),
            "deadline_seconds": self.deadline_seconds,
            "artifact_root": self.artifact_root,
            "source_hash": self.source_hash,
            "config_hash": self.config_hash,
            "launch_nonce": self.launch_nonce,
            "grace_seconds": self.grace_seconds,
        }

    def validated_paths(self) -> tuple[Path, Path]:
        root = Path(self.artifact_root).resolve()
        cwd = Path(self.cwd).resolve()
        executable = Path(self.argv[0]).resolve()
        if not root.is_dir():
            raise WorkerHostError("worker artifact root must already exist")
        if not cwd.is_dir() or not cwd.is_relative_to(root):
            raise WorkerHostError(
                "worker cwd must stay inside the admitted artifact root"
            )
        if not executable.is_absolute() or not executable.is_file():
            raise WorkerHostError("worker executable must be an existing absolute file")
        return root, cwd


@dataclass(frozen=True, slots=True)
class WorkerOwnership:
    pid: int
    creation_token: str
    launch_nonce: str
    source_hash: str
    config_hash: str
    spec_hash: str

    def to_object(self) -> JsonObject:
        return {
            "pid": self.pid,
            "creation_token": self.creation_token,
            "launch_nonce": self.launch_nonce,
            "source_hash": self.source_hash,
            "config_hash": self.config_hash,
            "spec_hash": self.spec_hash,
        }


def process_creation_token(pid: int) -> str:
    """Read an OS creation token so PID reuse cannot establish ownership."""

    if type(pid) is not int or pid <= 0:
        raise WorkerHostError("PID must be a positive integer")
    if os.name == "nt":
        kernel32: Any = ctypes.WinDLL(  # type: ignore[attr-defined]
            "kernel32", use_last_error=True
        )
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetProcessTimes.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            raise WorkerHostError("cannot open process for creation-time verification")

        class FileTime(ctypes.Structure):
            _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

        created = FileTime()
        exited = FileTime()
        kernel = FileTime()
        user = FileTime()
        kernel32.GetProcessTimes.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
        ]
        try:
            ok = kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            )
            if not ok:
                raise WorkerHostError("cannot read process creation time")
            return f"win:{(created.high << 32) | created.low}"
        finally:
            kernel32.CloseHandle(handle)

    stat = Path(f"/proc/{pid}/stat")
    if stat.is_file():
        text = stat.read_text(encoding="utf-8")
        closing = text.rfind(")")
        if closing < 0:
            raise WorkerHostError("cannot parse process creation token")
        fields = text[closing + 2 :].split()
        if len(fields) <= 19:
            raise WorkerHostError("process stat lacks creation token")
        return f"proc:{fields[19]}"

    raise WorkerHostError("OS process creation verification is unavailable")


class _WindowsJob:
    def __init__(self, pid: int) -> None:
        self._kernel32: Any = ctypes.WinDLL(  # type: ignore[attr-defined]
            "kernel32", use_last_error=True
        )
        self._kernel32.CreateJobObjectW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
        ]
        self._kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        self._kernel32.OpenProcess.restype = ctypes.c_void_p
        self._kernel32.SetInformationJobObject.restype = ctypes.c_int
        self._kernel32.AssignProcessToJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        self._kernel32.TerminateJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self._kernel32.TerminateJobObject.restype = ctypes.c_int
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.CloseHandle.restype = ctypes.c_int
        self._job: Any = self._kernel32.CreateJobObjectW(None, None)
        if not self._job:
            raise WorkerHostError("CreateJobObjectW failed")

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        info = ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00002000
        self._kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        ok = self._kernel32.SetInformationJobObject(
            self._job, 9, ctypes.byref(info), ctypes.sizeof(info)
        )
        if not ok:
            self.close()
            raise WorkerHostError("cannot enable kill-on-job-close")

        process = self._kernel32.OpenProcess(0x0100 | 0x0001, False, pid)
        if not process:
            self.close()
            raise WorkerHostError("cannot open child for Job Object assignment")
        try:
            if not self._kernel32.AssignProcessToJobObject(self._job, process):
                self.close()
                raise WorkerHostError("cannot assign child to Windows Job Object")
        finally:
            self._kernel32.CloseHandle(process)

    def terminate(self) -> None:
        if self._job and not self._kernel32.TerminateJobObject(self._job, 124):
            raise WorkerHostError("TerminateJobObject failed")

    def close(self) -> None:
        if getattr(self, "_job", None):
            self._kernel32.CloseHandle(self._job)
            self._job = None


def _terminate_process_tree(
    process: subprocess.Popen[bytes],
    job: _WindowsJob | None,
    *,
    grace_seconds: float,
) -> None:
    if process.poll() is not None:
        return
    if job is not None:
        break_signal = getattr(signal, "CTRL_BREAK_EVENT", None)
        if break_signal is not None:
            try:
                os.kill(process.pid, break_signal)
                process.wait(timeout=grace_seconds)
                return
            except (OSError, subprocess.TimeoutExpired):
                pass
        job.terminate()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return


def _write_json(path: Path, value: JsonObject) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_host(spec_path: str | Path) -> int:
    """Own one worker tree until exit, cancellation, or an independent hard deadline."""

    path = Path(spec_path).resolve()
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerHostError(f"cannot read worker spec: {exc}") from exc
    spec = WorkerSpec.from_object(value)
    root, cwd = spec.validated_paths()
    attempt = (root / spec.attempt_id).resolve()
    if not attempt.is_relative_to(root):
        raise WorkerHostError("attempt directory escapes artifact root")
    attempt.mkdir(parents=True, exist_ok=True)
    cancel_path = attempt / "cancel-request.json"
    complete_path = attempt / "host-complete.json"
    if complete_path.exists():
        raise WorkerHostError("worker host completion already exists")

    environment = dict(os.environ)
    environment.update(spec.environment)
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))

    started = time.monotonic()
    stdout_path = attempt / "worker.log"
    with stdout_path.open("wb") as log:
        process = subprocess.Popen(
            list(spec.argv),
            cwd=cwd,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            shell=False,
            start_new_session=os.name != "nt",
            creationflags=creationflags,
        )
        job: _WindowsJob | None = None
        try:
            if os.name == "nt":
                job = _WindowsJob(process.pid)
            reason = "exited"
            while process.poll() is None:
                if cancel_path.exists():
                    reason = "cancelled"
                    _terminate_process_tree(
                        process,
                        job,
                        grace_seconds=spec.grace_seconds,
                    )
                    break
                if time.monotonic() - started >= spec.deadline_seconds:
                    reason = "deadline"
                    _terminate_process_tree(
                        process,
                        job,
                        grace_seconds=spec.grace_seconds,
                    )
                    break
                time.sleep(0.05)
            returncode = process.wait()
        finally:
            if job is not None:
                job.close()

    record: JsonObject = {
        "schema": "ttt.worker_host_completion",
        "schema_version": 1,
        "attempt_id": spec.attempt_id,
        "launch_nonce": spec.launch_nonce,
        "source_hash": spec.source_hash,
        "config_hash": spec.config_hash,
        "spec_hash": content_hash(spec.to_object()),
        "reason": reason,
        "returncode": returncode,
        "elapsed_seconds": time.monotonic() - started,
        "worker_log": str(stdout_path),
        "admission_eligible": False,
    }
    _write_json(complete_path, record)
    return returncode if reason == "exited" else 124


def write_spec(path: str | Path, spec: WorkerSpec) -> str:
    """Persist a canonical immutable host spec and return its semantic hash."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing: object = json.loads(destination.read_text(encoding="utf-8"))
        if existing != spec.to_object():
            raise WorkerHostError("existing worker spec differs")
    else:
        destination.write_text(
            canonical_json(spec.to_object()) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return content_hash(spec.to_object())


def launch_worker_host(spec_path: str | Path) -> WorkerOwnership:
    """Detach a small host whose deadline and process tree survive controller exit."""

    path = Path(spec_path).resolve()
    value: object = json.loads(path.read_text(encoding="utf-8"))
    spec = WorkerSpec.from_object(value)
    spec.validated_paths()
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(
            getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    host = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "techrotic_training_triumvirate.experiments.worker",
            "--host",
            str(path),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )
    token = process_creation_token(host.pid)
    return WorkerOwnership(
        pid=host.pid,
        creation_token=token,
        launch_nonce=spec.launch_nonce,
        source_hash=spec.source_hash,
        config_hash=spec.config_hash,
        spec_hash=content_hash(spec.to_object()),
    )


def request_cancel(
    ownership: WorkerOwnership, cancel_path: str | Path, *, reason: str
) -> None:
    """Ask only the still-owned host to cancel its Job Object/process group."""

    if process_creation_token(ownership.pid) != ownership.creation_token:
        raise WorkerHostError("PID was reused or worker ownership no longer matches")
    path = Path(cancel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        path,
        {
            "reason": reason,
            "pid": ownership.pid,
            "creation_token": ownership.creation_token,
            "launch_nonce": ownership.launch_nonce,
            "source_hash": ownership.source_hash,
            "config_hash": ownership.config_hash,
            "spec_hash": ownership.spec_hash,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run_host(args.host)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"worker host failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
