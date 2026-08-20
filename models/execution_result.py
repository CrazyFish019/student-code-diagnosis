"""Data returned by the generic process runner."""

from dataclasses import dataclass
from enum import Enum

from core.exceptions import ModelValidationError


class ExecutionStatus(str, Enum):
    """Termination category for one process execution."""

    SUCCESS = "SUCCESS"
    TIMED_OUT = "TIMED_OUT"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    START_FAILED = "START_FAILED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Immutable outcome of one controlled process execution."""

    status: ExecutionStatus
    stdout: str
    stderr: str
    exit_code: int | None
    execution_time_ms: int
    error_message: str | None = None
    cleanup_error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExecutionStatus):
            raise ModelValidationError(
                "ExecutionResult.status must be an ExecutionStatus"
            )
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise ModelValidationError("ExecutionResult output fields must be strings")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ModelValidationError(
                "ExecutionResult.exit_code must be an int or None"
            )
        if (
            isinstance(self.execution_time_ms, bool)
            or not isinstance(self.execution_time_ms, int)
            or self.execution_time_ms < 0
        ):
            raise ModelValidationError(
                "ExecutionResult.execution_time_ms must be a non-negative integer"
            )
        for field_name in ("error_message", "cleanup_error"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise ModelValidationError(
                    f"ExecutionResult.{field_name} must be a string or None"
                )

    @property
    def timed_out(self) -> bool:
        return self.status is ExecutionStatus.TIMED_OUT
