"""Restart-safe worker host with owned-process verification and containment."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from techrotic_training_triumvirate.schemas import JsonObject, canonical_json

from .model import OrchestrationError


class WorkerContainmentError(OrchestrationError):
    """A worker cannot be launched, identified, bounded, or cancelled safely."""


def _windows_kernel32() -> Any:
    """Return kernel32 with pointer-width-safe signatures for worker ownership."""

    win_dll: Any = getattr(ctypes, "WinDLL")
    kernel32: Any = win_dll("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.OpenJobObjectW.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.OpenJobObjectW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _sha256(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise WorkerContainmentError(f"{field} must be a lowercase SHA-256")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise WorkerContainmentError(f"{field} must be a nonempty string")
    return value


def _positive_seconds(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise WorkerContainmentError(f"{field} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    """A fixed argv/environment contract consumed by the independent worker host."""

    attempt_id: str
    launch_nonce: str
    source_sha256: str
    config_sha256: str
    argv: tuple[str, ...]
    cwd: str
    environment: dict[str, str]
    deadline_seconds: int
    grace_seconds: int
    ownership_path: str
    stop_path: str
    result_path: str
    log_path: str

    def __post_init__(self) -> None:
        _sha256(self.attempt_id, field="attempt_id")
        _text(self.launch_nonce, field="launch_nonce")
        _sha256(self.source_sha256, field="source_sha256")
        _sha256(self.config_sha256, field="config_sha256")
        if not self.argv or any(not item or "\x00" in item for item in self.argv):
            raise WorkerContainmentError("worker argv must be a nonempty argv array")
        _text(self.cwd, field="cwd")
        _positive_seconds(self.deadline_seconds, field="deadline_seconds")
        _positive_seconds(self.grace_seconds, field="grace_seconds")
        for field_name, value in (
            ("ownership_path", self.ownership_path),
            ("stop_path", self.stop_path),
            ("result_path", self.result_path),
            ("log_path", self.log_path),
        ):
            _text(value, field=field_name)
        if any(
            "\x00" in key or "\x00" in value
            for key, value in self.environment.items()
        ):
            raise WorkerContainmentError("worker environment contains NUL")

    @property
    def job_name(self) -> str:
        safe = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in self.launch_nonce
        )
        return f"TTT-{safe[:96]}"

    def to_object(self) -> JsonObject:
        return {
            "attempt_id": self.attempt_id,
            "launch_nonce": self.launch_nonce,
            "source_sha256": self.source_sha256,
            "config_sha256": self.config_sha256,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "environment": dict(sorted(self.environment.items())),
            "deadline_seconds": self.deadline_seconds,
            "grace_seconds": self.grace_seconds,
            "ownership_path": self.ownership_path,
            "stop_path": self.stop_path,
            "result_path": self.result_path,
            "log_path": self.log_path,
        }

    @classmethod
    def from_object(cls, value: object) -> Self:
        if not isinstance(value, dict):
            raise WorkerContainmentError("worker spec must be a JSON object")
        required = {
            "attempt_id",
            "launch_nonce",
            "source_sha256",
            "config_sha256",
            "argv",
            "cwd",
            "environment",
            "deadline_seconds",
            "grace_seconds",
            "ownership_path",
            "stop_path",
            "result_path",
            "log_path",
        }
        if set(value) != required:
            raise WorkerContainmentError("worker spec fields differ from schema")
        argv = value["argv"]
        environment = value["environment"]
        if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
            raise WorkerContainmentError("worker argv must be an array of strings")
        if not isinstance(environment, dict) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in environment.items()
        ):
            raise WorkerContainmentError(
                "worker environment must map strings to strings"
            )
        return cls(
            attempt_id=_sha256(value["attempt_id"], field="attempt_id"),
            launch_nonce=_text(value["launch_nonce"], field="launch_nonce"),
            source_sha256=_sha256(value["source_sha256"], field="source_sha256"),
            config_sha256=_sha256(value["config_sha256"], field="config_sha256"),
            argv=tuple(argv),
            cwd=_text(value["cwd"], field="cwd"),
            environment=dict(environment),
            deadline_seconds=_positive_seconds(
                value["deadline_seconds"], field="deadline_seconds"
            ),
            grace_seconds=_positive_seconds(
                value["grace_seconds"], field="grace_seconds"
            ),
            ownership_path=_text(value["ownership_path"], field="ownership_path"),
            stop_path=_text(value["stop_path"], field="stop_path"),
            result_path=_text(value["result_path"], field="result_path"),
            log_path=_text(value["log_path"], field="log_path"),
        )


@dataclass(frozen=True, slots=True)
class OwnedProcess:
    """Process identity strong enough to refuse PID reuse."""

    pid: int
    creation_token: str
    attempt_id: str
    launch_nonce: str
    source_sha256: str
    config_sha256: str
    job_name: str

    def to_object(self) -> JsonObject:
        return {
            "pid": self.pid,
            "creation_token": self.creation_token,
            "attempt_id": self.attempt_id,
            "launch_nonce": self.launch_nonce,
            "source_sha256": self.source_sha256,
            "config_sha256": self.config_sha256,
            "job_name": self.job_name,
        }

    @classmethod
    def from_object(cls, value: object) -> Self:
        if not isinstance(value, dict):
            raise WorkerContainmentError("ownership record must be a JSON object")
        required = {
            "pid",
            "creation_token",
            "attempt_id",
            "launch_nonce",
            "source_sha256",
            "config_sha256",
            "job_name",
        }
        if set(value) != required:
            raise WorkerContainmentError("ownership record fields differ from schema")
        pid = value["pid"]
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise WorkerContainmentError("owned PID must be positive")
        return cls(
            pid=pid,
            creation_token=_text(value["creation_token"], field="creation_token"),
            attempt_id=_sha256(value["attempt_id"], field="attempt_id"),
            launch_nonce=_text(value["launch_nonce"], field="launch_nonce"),
            source_sha256=_sha256(value["source_sha256"], field="source_sha256"),
            config_sha256=_sha256(value["config_sha256"], field="config_sha256"),
            job_name=_text(value["job_name"], field="job_name"),
        )


def _atomic_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_worker_spec(path: str | Path, spec: WorkerSpec) -> None:
    _atomic_json(Path(path), spec.to_object())


def load_worker_spec(path: str | Path) -> WorkerSpec:
    try:
        value: object = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerContainmentError("worker spec is unreadable") from exc
    return WorkerSpec.from_object(value)


def load_owned_process(path: str | Path) -> OwnedProcess:
    try:
        value: object = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerContainmentError("ownership record is unreadable") from exc
    return OwnedProcess.from_object(value)


def _posix_creation_token(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    right = raw.rfind(")")
    if right < 0:
        return None
    fields = raw[right + 2 :].split()
    if len(fields) <= 19:
        return None
    return f"procfs-start:{fields[19]}"


def _windows_creation_token(pid: int) -> str | None:
    kernel32 = _windows_kernel32()
    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel_time = wintypes.FILETIME()
    user_time = wintypes.FILETIME()
    try:
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            return None
        value = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return f"win-filetime:{value}"
    finally:
        kernel32.CloseHandle(handle)


def process_creation_token(pid: int) -> str | None:
    """Return an OS-owned process creation identity, not a controller timestamp."""

    if pid <= 0:
        return None
    if os.name == "nt":
        return _windows_creation_token(pid)
    return _posix_creation_token(pid)


def verify_owned_process(owned: OwnedProcess) -> bool:
    """Require both PID and OS creation token to match before cancellation."""

    return process_creation_token(owned.pid) == owned.creation_token


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JobIoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimitInformation),
        ("IoInfo", _JobIoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WindowsJob:
    job_object_extended_limit_information = 9
    job_object_limit_kill_on_job_close = 0x00002000
    job_object_terminate = 0x0008

    def __init__(self, name: str) -> None:
        self._kernel32 = _windows_kernel32()
        self._handle = self._kernel32.CreateJobObjectW(None, name)
        if not self._handle:
            raise WorkerContainmentError("CreateJobObjectW failed")
        limits = _JobExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = (
            self.job_object_limit_kill_on_job_close
        )
        if not self._kernel32.SetInformationJobObject(
            self._handle,
            self.job_object_extended_limit_information,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            self.close()
            raise WorkerContainmentError("SetInformationJobObject failed")

    def assign(self, process: subprocess.Popen[bytes]) -> None:
        process_handle = getattr(process, "_handle", None)
        if process_handle is None or not self._kernel32.AssignProcessToJobObject(
            self._handle, process_handle
        ):
            raise WorkerContainmentError("AssignProcessToJobObject failed")

    def terminate(self, code: int = 1) -> None:
        if self._handle and not self._kernel32.TerminateJobObject(self._handle, code):
            raise WorkerContainmentError("TerminateJobObject failed")

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None

    @classmethod
    def terminate_named(cls, name: str, code: int = 1) -> None:
        kernel32 = _windows_kernel32()
        handle = kernel32.OpenJobObjectW(cls.job_object_terminate, False, name)
        if not handle:
            raise WorkerContainmentError("owned Windows Job Object is unavailable")
        try:
            if not kernel32.TerminateJobObject(handle, code):
                raise WorkerContainmentError("TerminateJobObject failed")
        finally:
            kernel32.CloseHandle(handle)


def _request_tree_stop(owned: OwnedProcess, *, force: bool) -> None:
    if not verify_owned_process(owned):
        raise WorkerContainmentError(
            "owned process identity changed; refusing to signal a reused PID"
        )
    if os.name == "nt":
        if force:
            _WindowsJob.terminate_named(owned.job_name)
            return
        try:
            os.kill(owned.pid, signal.SIGTERM)
        except OSError as exc:
            raise WorkerContainmentError("cannot request worker stop") from exc
        return
    try:
        os.killpg(owned.pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError as exc:
        raise WorkerContainmentError("cannot signal owned process group") from exc


def request_cancel(spec: WorkerSpec) -> None:
    """Persist a cancellation intent only after verifying current ownership."""

    owned = load_owned_process(spec.ownership_path)
    if (
        owned.attempt_id != spec.attempt_id
        or owned.launch_nonce != spec.launch_nonce
        or owned.source_sha256 != spec.source_sha256
        or owned.config_sha256 != spec.config_sha256
    ):
        raise WorkerContainmentError("ownership record does not match worker spec")
    if not verify_owned_process(owned):
        raise WorkerContainmentError(
            "owned process is absent or PID was reused; refusing cancellation"
        )
    _atomic_json(
        Path(spec.stop_path),
        {
            "schema": "ttt.worker_stop",
            "schema_version": 1,
            "attempt_id": spec.attempt_id,
            "launch_nonce": spec.launch_nonce,
        },
    )


def force_cancel_owned(spec: WorkerSpec) -> None:
    """Last-resort tree termination after a host failure, still identity-checked."""

    owned = load_owned_process(spec.ownership_path)
    if owned.attempt_id != spec.attempt_id or owned.launch_nonce != spec.launch_nonce:
        raise WorkerContainmentError("ownership record does not match worker spec")
    _request_tree_stop(owned, force=True)


def _wait_after_stop(
    process: subprocess.Popen[bytes],
    owned: OwnedProcess,
    grace_seconds: int,
) -> int:
    _request_tree_stop(owned, force=False)
    try:
        return process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        _request_tree_stop(owned, force=True)
        try:
            return process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise WorkerContainmentError("owned worker tree did not terminate") from exc


def run_worker_host(spec: WorkerSpec) -> JsonObject:
    """Launch one worker and enforce its deadline independently of the controller."""

    cwd = Path(spec.cwd).resolve()
    if not cwd.is_dir():
        raise WorkerContainmentError("worker cwd does not exist")
    for output_path in (
        Path(spec.ownership_path),
        Path(spec.stop_path),
        Path(spec.result_path),
        Path(spec.log_path),
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(spec.environment)
    log_path = Path(spec.log_path)
    started_ns = time.time_ns()
    start_monotonic = time.monotonic()
    job: _WindowsJob | None = None
    owned: OwnedProcess | None = None
    cancelled = False
    timed_out = False
    exit_code: int | None = None
    creation_flags = 0
    if os.name == "nt":
        creation_flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        job = _WindowsJob(spec.job_name)
    try:
        with log_path.open("ab", buffering=0) as log_handle:
            process = subprocess.Popen(
                list(spec.argv),
                cwd=str(cwd),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                shell=False,
                start_new_session=os.name != "nt",
                creationflags=creation_flags,
            )
            if job is not None:
                try:
                    job.assign(process)
                except BaseException:
                    process.kill()
                    process.wait()
                    raise
            creation_token = process_creation_token(process.pid)
            if creation_token is None:
                if job is not None:
                    job.terminate()
                else:
                    process.kill()
                process.wait()
                raise WorkerContainmentError(
                    "OS process creation identity could not be established"
                )
            owned = OwnedProcess(
                pid=process.pid,
                creation_token=creation_token,
                attempt_id=spec.attempt_id,
                launch_nonce=spec.launch_nonce,
                source_sha256=spec.source_sha256,
                config_sha256=spec.config_sha256,
                job_name=spec.job_name,
            )
            _atomic_json(Path(spec.ownership_path), owned.to_object())
            while True:
                polled = process.poll()
                if polled is not None:
                    exit_code = polled
                    break
                if Path(spec.stop_path).is_file():
                    cancelled = True
                    exit_code = _wait_after_stop(
                        process, owned, spec.grace_seconds
                    )
                    break
                if time.monotonic() - start_monotonic >= spec.deadline_seconds:
                    timed_out = True
                    exit_code = _wait_after_stop(
                        process, owned, spec.grace_seconds
                    )
                    break
                time.sleep(0.1)
    finally:
        if job is not None:
            job.close()
    if owned is None or exit_code is None:
        raise WorkerContainmentError("worker host ended without an owned result")
    result: JsonObject = {
        "schema": "ttt.worker_result",
        "schema_version": 1,
        "attempt_id": spec.attempt_id,
        "launch_nonce": spec.launch_nonce,
        "source_sha256": spec.source_sha256,
        "config_sha256": spec.config_sha256,
        "pid": owned.pid,
        "creation_token": owned.creation_token,
        "started_at_ns": started_ns,
        "finished_at_ns": time.time_ns(),
        "wall_seconds": max(0.0, time.monotonic() - start_monotonic),
        "exit_code": exit_code,
        "cancelled": cancelled,
        "timed_out": timed_out,
        "completed_successfully": exit_code == 0 and not cancelled and not timed_out,
    }
    _atomic_json(Path(spec.result_path), result)
    return result


def launch_detached_worker_host(spec_path: str | Path) -> int:
    """Start the deadline-owning host so controller exit cannot extend the worker."""

    path = Path(spec_path).resolve()
    if not path.is_file():
        raise WorkerContainmentError("worker spec file does not exist")
    creation_flags = 0
    if os.name == "nt":
        creation_flags = int(getattr(subprocess, "DETACHED_PROCESS", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    process = subprocess.Popen(
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
        close_fds=True,
        start_new_session=os.name != "nt",
        creationflags=creation_flags,
    )
    return process.pid


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ttt-experiment-worker-host")
    parser.add_argument("--host", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        spec = load_worker_spec(args.host)
        result = run_worker_host(spec)
    except WorkerContainmentError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0 if result["completed_successfully"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
