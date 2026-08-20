"""Judging status and result domain models."""

from dataclasses import dataclass, field
from enum import Enum

from core.exceptions import ModelValidationError


class JudgeStatus(str, Enum):
    """Possible states and outcomes of judging."""

    PENDING = "PENDING"
    AC = "AC"
    WA = "WA"
    CE = "CE"
    RE = "RE"
    TLE = "TLE"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass(frozen=True, slots=True)
class TestCaseResult:
    """Execution result for one test case."""

    testcase_id: str
    status: JudgeStatus
    execution_time_ms: int
    stdout: str
    stderr: str
    exit_code: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.testcase_id, str) or not self.testcase_id.strip():
            raise ModelValidationError(
                "TestCaseResult.testcase_id must be a non-empty string"
            )
        if not isinstance(self.status, JudgeStatus):
            raise ModelValidationError("TestCaseResult.status must be a JudgeStatus")
        if (
            isinstance(self.execution_time_ms, bool)
            or not isinstance(self.execution_time_ms, int)
            or self.execution_time_ms < 0
        ):
            raise ModelValidationError(
                "TestCaseResult.execution_time_ms must be a non-negative integer"
            )
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise ModelValidationError("TestCaseResult stdout and stderr must be strings")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ModelValidationError(
                "TestCaseResult.exit_code must be an integer or None"
            )


@dataclass(frozen=True, slots=True)
class JudgeResult:
    """Aggregate result whose statistics are derived from test case outcomes."""

    submission_id: str
    problem_id: str
    final_status: JudgeStatus
    testcase_results: tuple[TestCaseResult, ...]
    compile_stdout: str = ""
    compile_stderr: str = ""
    passed_count: int = field(init=False)
    total_count: int = field(init=False)

    def __post_init__(self) -> None:
        for field_name in ("submission_id", "problem_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"JudgeResult.{field_name} must be a non-empty string"
                )
        if not isinstance(self.final_status, JudgeStatus):
            raise ModelValidationError("JudgeResult.final_status must be a JudgeStatus")
        try:
            testcase_results = tuple(self.testcase_results)
        except TypeError as exc:
            raise ModelValidationError(
                "JudgeResult.testcase_results must be iterable"
            ) from exc
        if not all(isinstance(result, TestCaseResult) for result in testcase_results):
            raise ModelValidationError(
                "JudgeResult.testcase_results must contain only TestCaseResult values"
            )
        if len({result.testcase_id for result in testcase_results}) != len(
            testcase_results
        ):
            raise ModelValidationError(
                "JudgeResult.testcase_results must have unique testcase ids"
            )
        if not isinstance(self.compile_stdout, str) or not isinstance(
            self.compile_stderr, str
        ):
            raise ModelValidationError(
                "JudgeResult compile output fields must be strings"
            )

        object.__setattr__(self, "testcase_results", testcase_results)
        object.__setattr__(
            self,
            "passed_count",
            sum(result.status is JudgeStatus.AC for result in testcase_results),
        )
        object.__setattr__(self, "total_count", len(testcase_results))
