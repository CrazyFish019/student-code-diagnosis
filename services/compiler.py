"""C++ compilation service built on the controlled process runner."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Sequence
from uuid import uuid4

from models.compile_result import CompileResult, CompileStatus
from models.execution_result import ExecutionStatus
from services.process_runner import run_process


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _resolve_compiler(compiler: str | Path) -> Path | None:
    compiler_text = os.fspath(compiler)
    candidate = Path(compiler_text)
    if candidate.is_absolute() or candidate.parent != Path("."):
        resolved = candidate.resolve()
        return resolved if resolved.is_file() else None
    found = shutil.which(compiler_text)
    return Path(found).resolve() if found else None


def _output_path(output_dir: Path, output_name: str | None) -> Path:
    if output_name is None:
        output_name = f"submission-{uuid4().hex}"
    if not output_name or Path(output_name).name != output_name:
        raise ValueError("output_name must be a non-empty filename, not a path")
    if os.name == "nt" and Path(output_name).suffix.lower() != ".exe":
        output_name = f"{output_name}.exe"
    return output_dir / output_name


def compile_cpp(
    source_code: str,
    *,
    output_dir: str | Path,
    timeout_ms: int = 10_000,
    compiler: str | Path = "g++",
    output_name: str | None = None,
    extra_args: Sequence[str | Path] = (),
) -> CompileResult:
    """Compile C++17 source and return a structured, non-throwing outcome.

    On success, the returned executable belongs to the caller and must be
    deleted by the caller.  Temporary source files and every failed executable
    are removed by this function.
    """
    if not isinstance(source_code, str):
        raise TypeError("source_code must be a string")
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise ValueError("timeout_ms must be a positive integer")
    if not isinstance(compiler, (str, Path)):
        raise TypeError("compiler must be a string or Path")
    if isinstance(extra_args, (str, bytes)) or not all(
        isinstance(argument, (str, Path)) for argument in extra_args
    ):
        raise TypeError("extra_args must contain only strings or Paths")

    started_at = time.perf_counter()
    compiler_path = _resolve_compiler(compiler)
    if compiler_path is None:
        return CompileResult(
            status=CompileStatus.COMPILER_NOT_FOUND,
            executable_path=None,
            stdout="",
            stderr="",
            exit_code=None,
            execution_time_ms=_elapsed_ms(started_at),
            error_message=f"C++ compiler not found: {compiler}",
        )

    source_path: Path | None = None
    executable_path: Path | None = None
    keep_executable = False
    try:
        resolved_output_dir = Path(output_dir).resolve()
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        executable_path = _output_path(resolved_output_dir, output_name)
        if executable_path.exists():
            raise FileExistsError(
                f"refusing to overwrite existing executable: {executable_path}"
            )

        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".cpp",
            prefix="student-code-",
            dir=resolved_output_dir,
            delete=False,
        ) as source_file:
            source_file.write(source_code.encode("utf-8"))
            source_path = Path(source_file.name)

        execution = run_process(
            [
                compiler_path,
                source_path,
                "-std=c++17",
                "-O2",
                *extra_args,
                "-o",
                executable_path,
            ],
            stdin_data="",
            time_limit_ms=timeout_ms,
            temp_root=resolved_output_dir,
        )

        if execution.status is ExecutionStatus.SUCCESS:
            if not executable_path.is_file():
                return CompileResult(
                    status=CompileStatus.SYSTEM_ERROR,
                    executable_path=None,
                    stdout=execution.stdout,
                    stderr=execution.stderr,
                    exit_code=execution.exit_code,
                    execution_time_ms=execution.execution_time_ms,
                    error_message="compiler exited successfully but produced no executable",
                )
            keep_executable = True
            return CompileResult(
                status=CompileStatus.SUCCESS,
                executable_path=executable_path,
                stdout=execution.stdout,
                stderr=execution.stderr,
                exit_code=execution.exit_code,
                execution_time_ms=execution.execution_time_ms,
            )

        status_map = {
            ExecutionStatus.TIMED_OUT: CompileStatus.TIMED_OUT,
            ExecutionStatus.RUNTIME_ERROR: CompileStatus.COMPILE_ERROR,
            ExecutionStatus.START_FAILED: CompileStatus.START_FAILED,
            ExecutionStatus.SYSTEM_ERROR: CompileStatus.SYSTEM_ERROR,
        }
        return CompileResult(
            status=status_map[execution.status],
            executable_path=None,
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            execution_time_ms=execution.execution_time_ms,
            error_message=execution.error_message or execution.cleanup_error,
        )
    except Exception as exc:
        return CompileResult(
            status=CompileStatus.SYSTEM_ERROR,
            executable_path=None,
            stdout="",
            stderr="",
            exit_code=None,
            execution_time_ms=_elapsed_ms(started_at),
            error_message=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if source_path is not None:
            try:
                source_path.unlink(missing_ok=True)
            except OSError:
                pass
        # Successful artifacts are caller-owned; all other artifacts are ours.
        if executable_path is not None and not keep_executable:
            try:
                executable_path.unlink(missing_ok=True)
            except OSError:
                pass
