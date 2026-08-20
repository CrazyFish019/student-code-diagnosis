from datetime import datetime, timezone

import pytest

from models import (
    Diagnosis,
    JudgeResult,
    JudgeStatus,
    Problem,
    Submission,
    TestCase as DomainTestCase,
    TestCaseResult as DomainTestCaseResult,
)
from services.diagnosis_engine import diagnose_submission
from services.diagnosis_rules import DIAGNOSIS_RULES, RuleOutcome


def make_problem(inputs: tuple[str, ...]) -> Problem:
    return Problem(
        id="problem-1",
        title="Diagnostic problem",
        description="A deterministic diagnosis fixture.",
        time_limit_ms=500,
        memory_limit_mb=256,
        test_cases=tuple(
            DomainTestCase(f"case-{index}", input_data, f"{input_data.strip()}\n")
            for index, input_data in enumerate(inputs, start=1)
        ),
    )


def make_submission(source_code: str = "int main() { return 0; }\n") -> Submission:
    return Submission(
        id="submission-1",
        problem_id="problem-1",
        student_id="student-1",
        student_name="Alice",
        language="cpp",
        source_code=source_code,
        submitted_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )


def make_testcase_result(
    testcase_id: str,
    status: JudgeStatus,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = 0,
    execution_time_ms: int = 12,
) -> DomainTestCaseResult:
    return DomainTestCaseResult(
        testcase_id=testcase_id,
        status=status,
        execution_time_ms=execution_time_ms,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
    )


def judge_result(
    final_status: JudgeStatus,
    results: tuple[DomainTestCaseResult, ...] = (),
    *,
    compile_stderr: str = "",
) -> JudgeResult:
    return JudgeResult(
        submission_id="submission-1",
        problem_id="problem-1",
        final_status=final_status,
        testcase_results=results,
        compile_stderr=compile_stderr,
    )


def test_compile_error_rule_includes_compiler_stderr_and_line() -> None:
    problem = make_problem(("1\n",))
    stderr = "student-code.cpp:7:3: error: expected ';'\n"

    report = diagnose_submission(
        problem,
        make_submission(),
        judge_result(JudgeStatus.CE, compile_stderr=stderr),
    )

    assert report.category == "compile_error"
    assert report.summary == "程序无法编译"
    assert report.confidence == 1.0
    assert stderr in report.evidence
    assert report.related_lines == (7,)


def test_runtime_error_rule_contains_stderr_and_exit_code() -> None:
    problem = make_problem(("1\n",))
    result = make_testcase_result(
        "case-1",
        JudgeStatus.RE,
        stderr="abort message\n",
        exit_code=3,
    )

    report = diagnose_submission(
        problem,
        make_submission("int a[2]; int main() { return a[3]; }\n"),
        judge_result(JudgeStatus.RE, (result,)),
    )

    assert report.category == "runtime_error"
    assert report.confidence == 0.9
    assert any("exit_code=3" in item for item in report.evidence)
    assert any("abort message" in item for item in report.evidence)
    assert report.secondary_evidence


def test_generic_timeout_rule_produces_performance_issue() -> None:
    problem = make_problem(("10\n",))
    result = make_testcase_result(
        "case-1",
        JudgeStatus.TLE,
        exit_code=-1,
        execution_time_ms=530,
    )

    report = diagnose_submission(
        problem,
        make_submission("int main() { while (true) {} }\n"),
        judge_result(JudgeStatus.TLE, (result,)),
    )

    assert report.category == "performance_issue"
    assert report.summary == "程序运行时间超过限制"
    assert report.confidence == 0.9
    assert any("case-1" in item and "530" in item for item in report.evidence)


def test_whitespace_only_wrong_answers_produce_output_format_error() -> None:
    problem = Problem(
        id="problem-1",
        title="Formatting",
        description="Print two tokens.",
        time_limit_ms=500,
        memory_limit_mb=256,
        test_cases=(
            DomainTestCase("case-1", "", "1 2\n"),
            DomainTestCase("case-2", "", "3 4\n"),
        ),
    )
    results = (
        make_testcase_result("case-1", JudgeStatus.WA, stdout="  1   2\n"),
        make_testcase_result("case-2", JudgeStatus.WA, stdout="3    4\n"),
    )

    report = diagnose_submission(
        problem,
        make_submission(),
        judge_result(JudgeStatus.WA, results),
    )

    assert report.category == "output_format_error"
    assert report.confidence == 0.7
    assert len(report.evidence) == 2


def test_real_answer_difference_is_not_misdiagnosed_as_formatting() -> None:
    problem = Problem(
        id="problem-1",
        title="Values",
        description="Print values.",
        time_limit_ms=500,
        memory_limit_mb=256,
        test_cases=(
            DomainTestCase("case-1", "", "10\n"),
            DomainTestCase("case-2", "", "20\n"),
        ),
    )
    results = (
        make_testcase_result("case-1", JudgeStatus.WA, stdout="11\n"),
        make_testcase_result("case-2", JudgeStatus.WA, stdout="21\n"),
    )

    report = diagnose_submission(
        problem,
        make_submission(),
        judge_result(JudgeStatus.WA, results),
    )

    assert report.category is None
    assert report.secondary_evidence


def test_boundary_failures_produce_boundary_error() -> None:
    inputs = tuple(f"{number}\n" for number in (1, 2, 3, 4, 5, 6, 7, 8, 9, 100000))
    problem = make_problem(inputs)
    results = tuple(
        make_testcase_result(
            testcase.id,
            JudgeStatus.WA if index in (0, 9) else JudgeStatus.AC,
            stdout="wrong\n" if index in (0, 9) else testcase.expected_output,
        )
        for index, testcase in enumerate(problem.test_cases)
    )

    report = diagnose_submission(
        problem,
        make_submission("int main() { if (n == 1 || n >= 100000) {} }\n"),
        judge_result(JudgeStatus.WA, results),
    )

    assert report.category == "boundary_error"
    assert 0.6 <= report.confidence <= 0.85
    assert any("8/10" in item for item in report.evidence)
    assert report.secondary_evidence


def test_large_data_timeout_adds_complexity_evidence() -> None:
    problem = make_problem(("1\n", "100\n", "1000000\n"))
    results = (
        make_testcase_result("case-1", JudgeStatus.AC, stdout="1\n"),
        make_testcase_result("case-2", JudgeStatus.AC, stdout="100\n"),
        make_testcase_result(
            "case-3",
            JudgeStatus.TLE,
            exit_code=-1,
            execution_time_ms=520,
        ),
    )

    report = diagnose_submission(
        problem,
        make_submission(
            "int main() { for (;;) { for (;;) { break; } } }\n"
        ),
        judge_result(JudgeStatus.TLE, results),
    )

    assert report.category == "performance_issue"
    assert report.confidence == 0.95
    assert any("小规模" in item and "最大规模" in item for item in report.evidence)
    assert report.secondary_evidence


def test_rule_priority_is_declared_in_one_ordered_tuple() -> None:
    assert [rule.__name__ for rule in DIAGNOSIS_RULES] == [
        "compile_error_rule",
        "runtime_error_rule",
        "performance_issue_rule",
        "output_format_error_rule",
        "boundary_error_rule",
    ]


def test_engine_returns_first_matching_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def high_priority(context: object) -> RuleOutcome:
        return RuleOutcome(
            Diagnosis("runtime_error", "high", "detail", 0.9)
        )

    def low_priority(context: object) -> RuleOutcome:
        return RuleOutcome(
            Diagnosis("boundary_error", "low", "detail", 0.8)
        )

    monkeypatch.setattr(
        "services.diagnosis_engine.DIAGNOSIS_RULES",
        (high_priority, low_priority),
    )
    problem = make_problem(("1\n",))

    report = diagnose_submission(
        problem,
        make_submission(),
        judge_result(JudgeStatus.WA),
    )

    assert report.category == "runtime_error"
    assert report.summary == "high"
