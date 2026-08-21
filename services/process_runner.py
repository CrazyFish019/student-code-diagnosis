"""Controlled, shell-free execution of a single local process.

This module enforces a wall-clock timeout and attempts to terminate the entire
process tree.  It is a reliability boundary, not an operating-system sandbox.
"""

from __future__ import annotations

import locale
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from typing import Sequence

from core.config import TEMP_DIR
from models.execution_result import ExecutionResult, ExecutionStatus

_TERMINATION_GRACE_SECONDS = 0.2
_COMMUNICATE_CLEANUP_SECONDS = 2.0
_TASKKILL_TIMEOUT_SECONDS = 5.0


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _JobObjectBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JobObjectExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JobObjectBasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL

    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


def decode_captured_output(data: bytes | None) -> str:
    """Decode process output without ever failing on unknown byte sequences."""
    if not data:
        return ""

    encodings = ["utf-8", locale.getpreferredencoding(False)]
    if os.name == "nt":
        encodings.append("mbcs")

    tried: set[str] = set()
    for encoding in encodings:
        normalized = encoding.lower()
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _normalize_command(command: Sequence[str | Path]) -> list[str]:
    if isinstance(command, (str, bytes)) or not command:
        raise ValueError("command must be a non-empty sequence of arguments")

    normalized: list[str] = []
    for argument in command:
        if not isinstance(argument, (str, Path)):
            raise TypeError("every command argument must be a string or Path")
        normalized.append(os.fspath(argument))
    if not normalized[0]:
        raise ValueError("the executable argument cannot be empty")

    executable = Path(normalized[0])
    if executable.is_absolute() or executable.parent != Path(".") or executable.exists():
        normalized[0] = str(executable.resolve())
    return normalized


def _append_error(current: str | None, message: str) -> str:
    return message if current is None else f"{current}; {message}"


def _create_windows_job(proc: subprocess.Popen[bytes]) -> tuple[int | None, str | None]:
    """Put a process in a kill-on-close Job Object when Windows permits it."""
    if os.name != "nt":
        return None, None

    job_handle = _kernel32.CreateJobObjectW(None, None)
    if not job_handle:
        return None, f"CreateJobObjectW failed with Windows error {ctypes.get_last_error()}"

    information = _JobObjectExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    configured = _kernel32.SetInformationJobObject(
        job_handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(information),
        ctypes.sizeof(information),
    )
    if not configured:
        error = ctypes.get_last_error()
        _kernel32.CloseHandle(job_handle)
        return None, f"SetInformationJobObject failed with Windows error {error}"

    assigned = _kernel32.AssignProcessToJobObject(job_handle, int(proc._handle))
    if not assigned:
        error = ctypes.get_last_error()
        _kernel32.CloseHandle(job_handle)
        return None, f"AssignProcessToJobObject failed with Windows error {error}"
    return int(job_handle), None


def _close_windows_job(job_handle: int | None) -> None:
    if os.name == "nt" and job_handle is not None:
        _kernel32.CloseHandle(job_handle)


def _terminate_windows_process_tree(
    proc: subprocess.Popen[bytes], job_handle: int | None
) -> str | None:
    cleanup_error: str | None = None
    try:
        completed = subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=_TASKKILL_TIMEOUT_SECONDS,
            check=False,
        )
        if completed.returncode != 0 and proc.poll() is None:
            detail = decode_captured_output(completed.stderr).strip()
            cleanup_error = f"taskkill failed with exit code {completed.returncode}"
            if detail:
                cleanup_error = f"{cleanup_error}: {detail}"
    except (OSError, subprocess.SubprocessError) as exc:
        cleanup_error = f"taskkill failed: {type(exc).__name__}: {exc}"

    # A Job Object supplies a second, kernel-enforced tree boundary. This also
    # covers descendants that taskkill failed to discover in time.
    if job_handle is not None:
        if not _kernel32.TerminateJobObject(job_handle, 1):
            cleanup_error = _append_error(
                cleanup_error,
                f"TerminateJobObject failed with Windows error {ctypes.get_last_error()}",
            )

    if proc.poll() is None:
        try:
            proc.kill()
        except OSError as exc:
            cleanup_error = _append_error(
                cleanup_error, f"fallback process kill failed: {type(exc).__name__}: {exc}"
            )
    return cleanup_error


def _terminate_posix_process_tree(proc: subprocess.Popen[bytes]) -> str | None:
    cleanup_error: str | None = None
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return None
    except OSError as exc:
        cleanup_error = f"SIGTERM process-group cleanup failed: {exc}"

    deadline = time.monotonic() + _TERMINATION_GRACE_SECONDS
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)

    # Send SIGKILL to the group even if the group leader has exited: a child may
    # still be alive under the same process-group id.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError as exc:
        cleanup_error = _append_error(
            cleanup_error, f"SIGKILL process-group cleanup failed: {exc}"
        )

    if proc.poll() is None:
        try:
            proc.kill()
        except OSError as exc:
            cleanup_error = _append_error(
                cleanup_error, f"fallback process kill failed: {type(exc).__name__}: {exc}"
            )
    return cleanup_error


def _terminate_process_tree(
    proc: subprocess.Popen[bytes], job_handle: int | None
) -> str | None:
    if os.name == "nt":
        return _terminate_windows_process_tree(proc, job_handle)
    return _terminate_posix_process_tree(proc)


def _collect_after_timeout(
    proc: subprocess.Popen[bytes], job_handle: int | None
) -> tuple[bytes, bytes, str | None]:
    cleanup_error = _terminate_process_tree(proc, job_handle)
    try:
        stdout, stderr = proc.communicate(timeout=_COMMUNICATE_CLEANUP_SECONDS)
        return stdout or b"", stderr or b"", cleanup_error
    except subprocess.TimeoutExpired as exc:
        cleanup_error = _append_error(
            cleanup_error,
            "process pipes did not close after process-tree termination",
        )
        try:
            proc.kill()
        except OSError as kill_exc:
            cleanup_error = _append_error(
                cleanup_error, f"final process kill failed: {kill_exc}"
            )
        try:
            stdout, stderr = proc.communicate(timeout=_COMMUNICATE_CLEANUP_SECONDS)
            return stdout or b"", stderr or b"", cleanup_error
        except subprocess.TimeoutExpired:
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
            return exc.output or b"", exc.stderr or b"", cleanup_error


def run_process(
    command: Sequence[str | Path],
    *,
    stdin_data: str = "",
    time_limit_ms: int,
    temp_root: str | Path | None = None,
) -> ExecutionResult:
    """Run one command in a fresh temporary working directory.

    The command is always launched with ``shell=False``.  A bare executable name
    is resolved by the operating system; path-like executable arguments are made
    absolute before changing to the temporary working directory.
    """
    normalized_command = _normalize_command(command)
    if not isinstance(stdin_data, str):
        raise TypeError("stdin_data must be a string")
    if (
        isinstance(time_limit_ms, bool)
        or not isinstance(time_limit_ms, int)
        or time_limit_ms <= 0
    ):
        raise ValueError("time_limit_ms must be a positive integer")

    started_at = time.perf_counter()
    try:
        root = Path(temp_root).resolve() if temp_root is not None else TEMP_DIR
        root.mkdir(parents=True, exist_ok=True)
        temporary_parent = str(root)

        with tempfile.TemporaryDirectory(
            prefix="student-code-run-", dir=temporary_parent
        ) as working_directory:
            popen_options: dict[str, object] = {}
            if os.name == "nt":
                popen_options["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.CREATE_NO_WINDOW
                )
            else:
                popen_options["start_new_session"] = True

            try:
                proc = subprocess.Popen(
                    normalized_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=working_directory,
                    shell=False,
                    **popen_options,
                )
            except OSError as exc:
                return ExecutionResult(
                    status=ExecutionStatus.START_FAILED,
                    stdout="",
                    stderr="",
                    exit_code=None,
                    execution_time_ms=_elapsed_ms(started_at),
                    error_message=f"{type(exc).__name__}: {exc}",
                )

            job_handle: int | None = None
            job_setup_error: str | None = None
            if os.name == "nt":
                job_handle, job_setup_error = _create_windows_job(proc)
            try:
                try:
                    stdout_bytes, stderr_bytes = proc.communicate(
                        input=stdin_data.encode("utf-8", errors="replace"),
                        timeout=time_limit_ms / 1000,
                    )
                except subprocess.TimeoutExpired:
                    stdout_bytes, stderr_bytes, cleanup_error = _collect_after_timeout(
                        proc, job_handle
                    )
                    if job_setup_error is not None:
                        cleanup_error = _append_error(cleanup_error, job_setup_error)
                    return ExecutionResult(
                        status=ExecutionStatus.TIMED_OUT,
                        stdout=decode_captured_output(stdout_bytes),
                        stderr=decode_captured_output(stderr_bytes),
                        exit_code=proc.returncode,
                        execution_time_ms=_elapsed_ms(started_at),
                        cleanup_error=cleanup_error,
                    )

                status = (
                    ExecutionStatus.SUCCESS
                    if proc.returncode == 0
                    else ExecutionStatus.RUNTIME_ERROR
                )
                return ExecutionResult(
                    status=status,
                    stdout=decode_captured_output(stdout_bytes),
                    stderr=decode_captured_output(stderr_bytes),
                    exit_code=proc.returncode,
                    execution_time_ms=_elapsed_ms(started_at),
                )
            finally:
                _close_windows_job(job_handle)
    except Exception as exc:  # Infrastructure failures become explicit results.
        return ExecutionResult(
            status=ExecutionStatus.SYSTEM_ERROR,
            stdout="",
            stderr="",
            exit_code=None,
            execution_time_ms=_elapsed_ms(started_at),
            error_message=f"{type(exc).__name__}: {exc}",
        )
