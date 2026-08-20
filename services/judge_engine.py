"""Deterministic orchestration of compilation, execution, and comparison."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Callable

from core.config import TEMP_DIR
from core.exceptions import ModelValidationError
from models.compile_result import CompileResult, CompileStatus
from models.execution_result import ExecutionResult, ExecutionStatus
from models.judge_result import JudgeResult, JudgeStatus, TestCaseResult
from models.problem import Problem
from models.submission import Submission
from services.compiler import compile_cpp
from services.output_compare import compare_output
from services.process_runner import run_process

CompilerService = Callable[..., CompileResult]
ProcessRunner = Callable[..., ExecutionResult]

_FINAL_STATUS_PRIORITY: tuple[JudgeStatus, ...] = (
    JudgeStatus.SYSTEM_ERROR,
    JudgeStatus.TLE,
    JudgeStatus.RE,
    JudgeStatus.WA,
)

_EXECUTION_STATUS_MAP: dict[ExecutionStatus, JudgeStatus] = {
    ExecutionStatus.TIMED_OUT: JudgeStatus.TLE,
    ExecutionStatus.RUNTIME_ERROR: JudgeStatus.RE,
    ExecutionStatus.START_FAILED: JudgeStatus.SYSTEM_ERROR,
    ExecutionStatus.SYSTEM_ERROR: JudgeStatus.SYSTEM_ERROR,
}


def determine_final_status(
    testcase_results: tuple[TestCaseResult, ...] | list[TestCaseResult],
) -> JudgeStatus:
    """Apply the single, explicit priority rule for executed test cases."""
    statuses = {result.status for result in testcase_results}
    for status in _FINAL_STATUS_PRIORITY:
        if status in statuses:
            return status
    return JudgeStatus.AC


def _compile_diagnostics(result: CompileResult) -> str:
    if not result.error_message or result.error_message in result.stderr:
        return result.stderr
    separator = "" if not result.stderr else "\n"
    return f"{result.stderr}{separator}{result.error_message}"


def _failed_compile_result(
    problem: Problem,
    submission: Submission,
    compile_result: CompileResult,
) -> JudgeResult:
    final_status = (
        JudgeStatus.CE
        if compile_result.status is CompileStatus.COMPILE_ERROR
        else JudgeStatus.SYSTEM_ERROR
    )
    return JudgeResult(
        submission_id=submission.id,
        problem_id=problem.id,
        final_status=final_status,
        testcase_results=(),
        compile_stdout=compile_result.stdout,
        compile_stderr=_compile_diagnostics(compile_result),
    )


def _system_error_result(
    problem: Problem,
    submission: Submission,
    message: str,
) -> JudgeResult:
    return JudgeResult(
        submission_id=submission.id,
        problem_id=problem.id,
        final_status=JudgeStatus.SYSTEM_ERROR,
        testcase_results=(),
        compile_stderr=message,
    )


def _judge_testcase(
    executable_path: Path,
    *,
    testcase_id: str,
    input_data: str,
    expected_output: str,
    time_limit_ms: int,
    temp_root: Path,
    process_runner: ProcessRunner,
) -> TestCaseResult:
    try:
        execution = process_runner(
            [executable_path],
            stdin_data=input_data,
            time_limit_ms=time_limit_ms,
            temp_root=temp_root,
        )
    except Exception as exc:
        return TestCaseResult(
            testcase_id=testcase_id,
            status=JudgeStatus.SYSTEM_ERROR,
            execution_time_ms=0,
            stdout="",
            stderr=f"Process runner raised {type(exc).__name__}: {exc}",
            exit_code=None,
        )

    if execution.status is ExecutionStatus.SUCCESS:
        status = (
            JudgeStatus.AC
            if compare_output(expected_output, execution.stdout)
            else JudgeStatus.WA
        )
    else:
        status = _EXECUTION_STATUS_MAP[execution.status]

    return TestCaseResult(
        testcase_id=testcase_id,
        status=status,
        execution_time_ms=execution.execution_time_ms,
        stdout=execution.stdout,
        stderr=execution.stderr,
        exit_code=execution.exit_code,
    )


def judge_submission(
    problem: Problem,
    submission: Submission,
    *,
    compiler: str | Path = "g++",
    compile_timeout_ms: int = 10_000,
    temp_root: str | Path | None = None,
    compiler_service: CompilerService = compile_cpp,
    process_runner: ProcessRunner = run_process,
) -> JudgeResult:
    """Compile once, run every test case in order, and aggregate a JudgeResult."""
    if not isinstance(problem, Problem):
        raise TypeError("problem must be a Problem")
    if not isinstance(submission, Submission):
        raise TypeError("submission must be a Submission")
    if submission.problem_id != problem.id:
        raise ModelValidationError(
            "Submission.problem_id must match the judged Problem.id"
        )
    if (
        isinstance(compile_timeout_ms, bool)
        or not isinstance(compile_timeout_ms, int)
        or compile_timeout_ms <= 0
    ):
        raise ValueError("compile_timeout_ms must be a positive integer")

    try:
        root = Path(temp_root).resolve() if temp_root is not None else TEMP_DIR
        root.mkdir(parents=True, exist_ok=True)
        temporary_parent = os.fspath(root)

        with tempfile.TemporaryDirectory(
            prefix="student-code-judge-", dir=temporary_parent
        ) as judge_directory_text:
            judge_directory = Path(judge_directory_text)
            try:
                compile_result = compiler_service(
                    submission.source_code,
                    output_dir=judge_directory,
                    timeout_ms=compile_timeout_ms,
                    compiler=compiler,
                    output_name="submission",
                )
            except Exception as exc:
                return _system_error_result(
                    problem,
                    submission,
                    f"Compiler service raised {type(exc).__name__}: {exc}",
                )

            if compile_result.status is not CompileStatus.SUCCESS:
                return _failed_compile_result(problem, submission, compile_result)

            assert compile_result.executable_path is not None
            testcase_results = tuple(
                _judge_testcase(
                    compile_result.executable_path,
                    testcase_id=testcase.id,
                    input_data=testcase.input_data,
                    expected_output=testcase.expected_output,
                    time_limit_ms=problem.time_limit_ms,
                    temp_root=judge_directory,
                    process_runner=process_runner,
                )
                for testcase in problem.test_cases
            )
            return JudgeResult(
                submission_id=submission.id,
                problem_id=problem.id,
                final_status=determine_final_status(testcase_results),
                testcase_results=testcase_results,
                compile_stdout=compile_result.stdout,
                compile_stderr=compile_result.stderr,
            )
    except Exception as exc:
        return _system_error_result(
            problem,
            submission,
            f"Judge infrastructure raised {type(exc).__name__}: {exc}",
        )
