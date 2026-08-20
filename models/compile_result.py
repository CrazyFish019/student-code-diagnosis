"""Data returned by the C++ compiler service."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from core.exceptions import ModelValidationError


class CompileStatus(str, Enum):
    """Termination category for one compilation attempt."""

    SUCCESS = "SUCCESS"
    COMPILE_ERROR = "COMPILE_ERROR"
    TIMED_OUT = "TIMED_OUT"
    COMPILER_NOT_FOUND = "COMPILER_NOT_FOUND"
    START_FAILED = "START_FAILED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass(frozen=True, slots=True)
class CompileResult:
    """Immutable outcome of compiling one source file."""

    status: CompileStatus
    executable_path: Path | None
    stdout: str
    stderr: str
    exit_code: int | None
    execution_time_ms: int
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CompileStatus):
            raise ModelValidationError("CompileResult.status must be a CompileStatus")
        if self.executable_path is not None and not isinstance(
            self.executable_path, Path
        ):
            raise ModelValidationError(
                "CompileResult.executable_path must be a Path or None"
            )
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise ModelValidationError("CompileResult output fields must be strings")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ModelValidationError("CompileResult.exit_code must be an int or None")
        if (
            isinstance(self.execution_time_ms, bool)
            or not isinstance(self.execution_time_ms, int)
            or self.execution_time_ms < 0
        ):
            raise ModelValidationError(
                "CompileResult.execution_time_ms must be a non-negative integer"
            )
        if self.error_message is not None and not isinstance(self.error_message, str):
            raise ModelValidationError(
                "CompileResult.error_message must be a string or None"
            )
        if self.status is CompileStatus.SUCCESS and self.executable_path is None:
            raise ModelValidationError(
                "A successful CompileResult must contain executable_path"
            )
        if self.status is not CompileStatus.SUCCESS and self.executable_path is not None:
            raise ModelValidationError(
                "A failed CompileResult cannot contain executable_path"
            )

    @property
    def success(self) -> bool:
        return self.status is CompileStatus.SUCCESS

    @property
    def timed_out(self) -> bool:
        return self.status is CompileStatus.TIMED_OUT
