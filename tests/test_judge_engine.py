from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Callable

import pytest

from core.exceptions import ModelValidationError
from models import (
    CompileResult,
    CompileStatus,
    ExecutionResult,
    ExecutionStatus,
    JudgeStatus,
    Problem,
    Submission,
    TestCase as DomainTestCase,
    TestCaseResult as DomainTestCaseResult,
)
from services.judge_engine import determine_final_status, judge_submission


def make_problem(test_cases: tuple[DomainTestCase, ...] | None = None) -> Problem:
    if test_cases is None:
        test_cases = tuple(
            DomainTestCase(f"case-{number}", f"{number} {number + 1}\n", f"{number * 2 + 1}\n")
            for number in range(10)
        )
    return Problem(
        id="a-plus-b",
        title="A + B",
        description="Add two integers.",
        time_limit_ms=500,
        memory_limit_mb=256,
        test_cases=test_cases,
    )


def make_submission(source_code: str = "int main() {}\n") -> Submission:
    return Submission(
        id="submission-1",
        problem_id="a-plus-b",
        student_id="student-1",
        student_name="Alice",
        language="cpp",
        source_code=source_code,
        submitted_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )


class SuccessfulCompiler:
    def __init__(self) -> None:
        self.call_count = 0
        self.output_directories: list[Path] = []

    def __call__(
        self,
        source_code: str,
        *,
        output_dir: str | Path,
        timeout_ms: int,
        compiler: str | Path,
        output_name: str,
    ) -> CompileResult:
        self.call_count += 1
        directory = Path(output_dir)
        self.output_directories.append(directory)
        suffix = ".exe" if os.name == "nt" else ""
        executable = directory / f"{output_name}{suffix}"
        executable.write_bytes(b"fake executable")
        return CompileResult(
            status=CompileStatus.SUCCESS,
            executable_path=executable,
            stdout="compiler stdout",
            stderr="",
            exit_code=0,
            execution_time_ms=10,
        )


def execution(
    status: ExecutionStatus,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = 0,
) -> ExecutionResult:
    return ExecutionResult(
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        execution_time_ms=12,
    )


def adding_runner(
    command: list[Path],
    *,
    stdin_data: str,
    time_limit_ms: int,
    temp_root: Path,
) -> ExecutionResult:
    numbers = [int(value) for value in stdin_data.split()]
    output = "" if not numbers else f"{sum(numbers)}\n"
    return execution(ExecutionStatus.SUCCESS, stdout=output)


def test_correct_program_passes_all_ten_testcases() -> None:
    compiler = SuccessfulCompiler()

    result = judge_submission(
        make_problem(),
        make_submission(),
        compiler_service=compiler,
        process_runner=adding_runner,
    )

    assert result.final_status is JudgeStatus.AC
    assert result.passed_count == 10
    assert result.total_count == 10
    assert all(item.status is JudgeStatus.AC for item in result.testcase_results)


def test_one_wrong_testcase_produces_wa_and_correct_statistics() -> None:
    calls = 0

    def one_wrong_runner(*args: object, **kwargs: object) -> ExecutionResult:
        nonlocal calls
        calls += 1
        correct = adding_runner(*args, **kwargs)  # type: ignore[arg-type]
        if calls == 4:
            return execution(ExecutionStatus.SUCCESS, stdout="wrong\n")
        return correct

    result = judge_submission(
        make_problem(),
        make_submission(),
        compiler_service=SuccessfulCompiler(),
        process_runner=one_wrong_runner,
    )

    assert result.final_status is JudgeStatus.WA
    assert result.passed_count == 9
    assert result.total_count == 10
    assert result.testcase_results[3].status is JudgeStatus.WA


def test_compile_error_produces_ce_without_running_testcases() -> None:
    runner_called = False

    def failed_compiler(*args: object, **kwargs: object) -> CompileResult:
        return CompileResult(
            status=CompileStatus.COMPILE_ERROR,
            executable_path=None,
            stdout="",
            stderr="syntax error\n",
            exit_code=1,
            execution_time_ms=20,
        )

    def forbidden_runner(*args: object, **kwargs: object) -> ExecutionResult:
        nonlocal runner_called
        runner_called = True
        raise AssertionError("runner must not be called after a compile error")

    result = judge_submission(
        make_problem(),
        make_submission(),
        compiler_service=failed_compiler,
        process_runner=forbidden_runner,
    )

    assert result.final_status is JudgeStatus.CE
    assert result.compile_stderr == "syntax error\n"
    assert result.total_count == 0
    assert not runner_called


@pytest.mark.parametrize(
    ("execution_status", "expected_status", "exit_code"),
    [
        (ExecutionStatus.RUNTIME_ERROR, JudgeStatus.RE, 7),
        (ExecutionStatus.TIMED_OUT, JudgeStatus.TLE, -1),
        (ExecutionStatus.START_FAILED, JudgeStatus.SYSTEM_ERROR, None),
        (ExecutionStatus.SYSTEM_ERROR, JudgeStatus.SYSTEM_ERROR, None),
    ],
)
def test_execution_status_mapping(
    execution_status: ExecutionStatus,
    expected_status: JudgeStatus,
    exit_code: int | None,
) -> None:
    def runner(*args: object, **kwargs: object) -> ExecutionResult:
        return execution(execution_status, stderr="failure", exit_code=exit_code)

    problem = make_problem((DomainTestCase("only", "", ""),))
    result = judge_submission(
        problem,
        make_submission(),
        compiler_service=SuccessfulCompiler(),
        process_runner=runner,
    )

    assert result.final_status is expected_status
    assert result.testcase_results[0].status is expected_status
    assert result.testcase_results[0].exit_code == exit_code


def test_compiler_is_called_exactly_once_for_many_testcases() -> None:
    compiler = SuccessfulCompiler()

    judge_submission(
        make_problem(),
        make_submission(),
        compiler_service=compiler,
        process_runner=adding_runner,
    )

    assert compiler.call_count == 1


def test_testcases_run_in_problem_order() -> None:
    seen_inputs: list[str] = []
    cases = (
        DomainTestCase("third-id", "first\n", "ok\n"),
        DomainTestCase("first-id", "second\n", "ok\n"),
        DomainTestCase("second-id", "third\n", "ok\n"),
    )

    def recording_runner(*args: object, **kwargs: object) -> ExecutionResult:
        seen_inputs.append(str(kwargs["stdin_data"]))
        return execution(ExecutionStatus.SUCCESS, stdout="ok\n")

    result = judge_submission(
        make_problem(cases),
        make_submission(),
        compiler_service=SuccessfulCompiler(),
        process_runner=recording_runner,
    )

    assert seen_inputs == ["first\n", "second\n", "third\n"]
    assert [item.testcase_id for item in result.testcase_results] == [
        "third-id",
        "first-id",
        "second-id",
    ]


def test_final_status_uses_explicit_priority() -> None:
    results = [
        DomainTestCaseResult("wa", JudgeStatus.WA, 1, "", "", 0),
        DomainTestCaseResult("re", JudgeStatus.RE, 1, "", "", 1),
        DomainTestCaseResult("tle", JudgeStatus.TLE, 1, "", "", -1),
        DomainTestCaseResult("system", JudgeStatus.SYSTEM_ERROR, 1, "", "", None),
    ]

    assert determine_final_status(results) is JudgeStatus.SYSTEM_ERROR
    assert determine_final_status(results[:-1]) is JudgeStatus.TLE
    assert determine_final_status(results[:2]) is JudgeStatus.RE
    assert determine_final_status(results[:1]) is JudgeStatus.WA
    assert determine_final_status([]) is JudgeStatus.AC


def test_problem_without_testcases_is_ac_zero_of_zero() -> None:
    compiler = SuccessfulCompiler()
    result = judge_submission(
        make_problem(()),
        make_submission(),
        compiler_service=compiler,
        process_runner=adding_runner,
    )

    assert result.final_status is JudgeStatus.AC
    assert result.passed_count == 0
    assert result.total_count == 0
    assert compiler.call_count == 1


def test_empty_input_and_empty_output_testcase() -> None:
    result = judge_submission(
        make_problem((DomainTestCase("empty", "", ""),)),
        make_submission(),
        compiler_service=SuccessfulCompiler(),
        process_runner=adding_runner,
    )

    assert result.final_status is JudgeStatus.AC
    assert result.testcase_results[0].stdout == ""


def test_judge_workspace_path_with_spaces(tmp_path: Path) -> None:
    compiler = SuccessfulCompiler()
    root = tmp_path / "judge workspace with spaces"
    seen_executables: list[Path] = []

    def runner(command: list[Path], **kwargs: object) -> ExecutionResult:
        seen_executables.append(Path(command[0]))
        return adding_runner(command, **kwargs)  # type: ignore[arg-type]

    result = judge_submission(
        make_problem((DomainTestCase("one", "1 2\n", "3\n"),)),
        make_submission(),
        temp_root=root,
        compiler_service=compiler,
        process_runner=runner,
    )

    assert result.final_status is JudgeStatus.AC
    assert "judge workspace with spaces" in str(compiler.output_directories[0])
    assert "judge workspace with spaces" in str(seen_executables[0])
    assert not list(root.glob("student-code-judge-*"))


def test_compiler_infrastructure_failure_is_system_error() -> None:
    def missing_compiler(*args: object, **kwargs: object) -> CompileResult:
        return CompileResult(
            status=CompileStatus.COMPILER_NOT_FOUND,
            executable_path=None,
            stdout="",
            stderr="",
            exit_code=None,
            execution_time_ms=0,
            error_message="g++ not found",
        )

    result = judge_submission(
        make_problem(),
        make_submission(),
        compiler_service=missing_compiler,
        process_runner=adding_runner,
    )

    assert result.final_status is JudgeStatus.SYSTEM_ERROR
    assert "g++ not found" in result.compile_stderr


def test_submission_must_belong_to_problem() -> None:
    submission = Submission(
        id="submission-1",
        problem_id="different-problem",
        student_id="student-1",
        student_name="Alice",
        language="cpp",
        source_code="",
        submitted_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ModelValidationError, match="problem_id"):
        judge_submission(make_problem(), submission)
