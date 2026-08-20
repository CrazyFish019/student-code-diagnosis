"""Sanitized evidence imported from an authorized Vesibay submission."""

from __future__ import annotations

from dataclasses import dataclass

from core.exceptions import ModelValidationError
from models.execution_result import ExecutionStatus
from models.imported_problem import ImportedProblem


@dataclass(frozen=True, slots=True)
class OJCaseEvidence:
    case_id: str
    status: str
    execution_time_ms: int | None
    memory_bytes: int | None
    input_data: str
    expected_output: str
    user_output: str
    error_message: str = ""
    local_execution_status: ExecutionStatus | None = None
    locally_captured_stdout: str | None = None
    locally_captured_stderr: str | None = None
    local_exit_code: int | None = None
    local_execution_time_ms: int | None = None
    local_error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ModelValidationError("OJCaseEvidence.case_id must be non-empty")
        if not isinstance(self.status, str) or not self.status.strip():
            raise ModelValidationError("OJCaseEvidence.status must be non-empty")
        for name in ("execution_time_ms", "memory_bytes"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ModelValidationError(f"OJCaseEvidence.{name} is invalid")
        for name in ("input_data", "expected_output", "user_output", "error_message"):
            if not isinstance(getattr(self, name), str):
                raise ModelValidationError(f"OJCaseEvidence.{name} must be a string")
        if self.local_execution_status is None:
            if any(
                value is not None
                for value in (
                    self.locally_captured_stdout,
                    self.locally_captured_stderr,
                    self.local_exit_code,
                    self.local_execution_time_ms,
                    self.local_error_message,
                )
            ):
                raise ModelValidationError(
                    "local execution fields require local_execution_status"
                )
            return
        if not isinstance(self.local_execution_status, ExecutionStatus):
            raise ModelValidationError("local_execution_status is invalid")
        for name in ("locally_captured_stdout", "locally_captured_stderr"):
            if not isinstance(getattr(self, name), str):
                raise ModelValidationError(f"OJCaseEvidence.{name} must be a string")
        if self.local_exit_code is not None and (
            isinstance(self.local_exit_code, bool)
            or not isinstance(self.local_exit_code, int)
        ):
            raise ModelValidationError("local_exit_code must be an int or None")
        if (
            isinstance(self.local_execution_time_ms, bool)
            or not isinstance(self.local_execution_time_ms, int)
            or self.local_execution_time_ms < 0
        ):
            raise ModelValidationError(
                "local_execution_time_ms must be a non-negative integer"
            )
        if self.local_error_message is not None and not isinstance(
            self.local_error_message, str
        ):
            raise ModelValidationError("local_error_message must be a string or None")


@dataclass(frozen=True, slots=True)
class VesibaySubmissionEvidence:
    submission_id: str
    problem: ImportedProblem
    source_code: str
    final_status: str
    score: float | None
    cases: tuple[OJCaseEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.submission_id, str) or not self.submission_id.strip():
            raise ModelValidationError("submission_id must be non-empty")
        if not isinstance(self.problem, ImportedProblem):
            raise ModelValidationError("problem must be an ImportedProblem")
        if not isinstance(self.source_code, str) or not self.source_code.strip():
            raise ModelValidationError("source_code must be non-empty")
        if not isinstance(self.final_status, str) or not self.final_status.strip():
            raise ModelValidationError("final_status must be non-empty")
        if self.score is not None and (
            isinstance(self.score, bool) or not isinstance(self.score, (int, float))
        ):
            raise ModelValidationError("score must be numeric or None")
        cases = tuple(self.cases)
        if not all(isinstance(item, OJCaseEvidence) for item in cases):
            raise ModelValidationError("cases must contain OJCaseEvidence values")
        object.__setattr__(self, "cases", cases)
