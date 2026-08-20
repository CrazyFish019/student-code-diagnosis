import pytest

from core.exceptions import ModelValidationError
from models import JudgeResult, JudgeStatus, TestCaseResult as DomainTestCaseResult


def case_result(testcase_id: str, status: JudgeStatus) -> DomainTestCaseResult:
    return DomainTestCaseResult(
        testcase_id=testcase_id,
        status=status,
        execution_time_ms=12,
        stdout="output\n",
        stderr="",
        exit_code=0,
    )


def test_all_judge_status_values_are_available() -> None:
    assert {status.value for status in JudgeStatus} == {
        "PENDING",
        "AC",
        "WA",
        "CE",
        "RE",
        "TLE",
        "SYSTEM_ERROR",
    }


def test_testcase_result_creation_and_newline_preservation() -> None:
    result = case_result("case-1", JudgeStatus.AC)

    assert result.stdout == "output\n"
    assert result.exit_code == 0


def test_judge_result_derives_consistent_counts_and_tuple() -> None:
    result = JudgeResult(
        submission_id="s-1",
        problem_id="p-1",
        final_status=JudgeStatus.WA,
        testcase_results=[
            case_result("case-1", JudgeStatus.AC),
            case_result("case-2", JudgeStatus.WA),
            case_result("case-3", JudgeStatus.AC),
        ],
    )

    assert result.passed_count == 2
    assert result.total_count == 3
    assert isinstance(result.testcase_results, tuple)


def test_judge_result_counts_cannot_be_supplied_inconsistently() -> None:
    with pytest.raises(TypeError):
        JudgeResult(
            submission_id="s-1",
            problem_id="p-1",
            final_status=JudgeStatus.AC,
            testcase_results=(case_result("case-1", JudgeStatus.AC),),
            passed_count=0,  # type: ignore[call-arg]
        )


def test_judge_result_rejects_duplicate_testcase_ids() -> None:
    with pytest.raises(ModelValidationError, match="unique"):
        JudgeResult(
            submission_id="s-1",
            problem_id="p-1",
            final_status=JudgeStatus.WA,
            testcase_results=(
                case_result("same", JudgeStatus.AC),
                case_result("same", JudgeStatus.WA),
            ),
        )


def test_testcase_result_rejects_negative_execution_time() -> None:
    with pytest.raises(ModelValidationError, match="execution_time_ms"):
        DomainTestCaseResult("case-1", JudgeStatus.RE, -1, "", "error", 1)
