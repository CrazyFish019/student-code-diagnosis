from pathlib import Path

from models import (
    DiagnosisReport,
    JudgeResult,
    JudgeStatus,
    Problem,
    StudentSource,
    TestCase as DomainTestCase,
    TestCaseResult as DomainTestCaseResult,
)
from services.teacher_workflow import analyze_class


def make_problem() -> Problem:
    return Problem(
        id="problem-1",
        title="A+B",
        description="",
        time_limit_ms=500,
        memory_limit_mb=256,
        test_cases=(DomainTestCase("case-1", "1 2\n", "3\n"),),
    )


def fake_result(submission_id: str, status: JudgeStatus) -> JudgeResult:
    return JudgeResult(
        submission_id=submission_id,
        problem_id="problem-1",
        final_status=status,
        testcase_results=(
            DomainTestCaseResult(
                "case-1",
                JudgeStatus.AC if status is JudgeStatus.AC else status,
                10,
                "3\n",
                "",
                0,
            ),
        ),
    )


def test_workflow_calls_services_in_student_order(
    monkeypatch: object,
) -> None:
    judged_names: list[str] = []
    diagnosed_names: list[str] = []
    progress: list[tuple[int, int, str]] = []

    def fake_judge(problem: object, submission: object, **kwargs: object) -> JudgeResult:
        judged_names.append(submission.student_name)  # type: ignore[attr-defined]
        return fake_result(submission.id, JudgeStatus.AC)  # type: ignore[attr-defined]

    def fake_diagnose(
        problem: object, submission: object, judged: JudgeResult
    ) -> DiagnosisReport:
        diagnosed_names.append(submission.student_name)  # type: ignore[attr-defined]
        return DiagnosisReport(submission.id, "problem-1", None)  # type: ignore[attr-defined]

    monkeypatch.setattr("services.teacher_workflow.judge_submission", fake_judge)  # type: ignore[attr-defined]
    monkeypatch.setattr("services.teacher_workflow.diagnose_submission", fake_diagnose)  # type: ignore[attr-defined]
    students = (
        StudentSource("张三", "张三.cpp", "int main() {}"),
        StudentSource("李四", "李四.cpp", "int main() {}"),
    )

    result = analyze_class(
        make_problem(),
        standard_source_code="int main() {}",
        students=students,
        compiler=Path("g++"),
        progress_callback=lambda done, total, name: progress.append(
            (done, total, name)
        ),
    )

    assert judged_names == ["标准程序", "张三", "李四"]
    assert diagnosed_names == ["张三", "李四"]
    assert [item.student_name for item in result.students] == ["张三", "李四"]
    assert progress == [(1, 2, "张三"), (2, 2, "李四")]


def test_one_student_exception_does_not_abort_class(
    monkeypatch: object,
) -> None:
    def fake_judge(problem: object, submission: object, **kwargs: object) -> JudgeResult:
        if submission.student_name == "失败学生":  # type: ignore[attr-defined]
            raise RuntimeError("isolated failure")
        return fake_result(submission.id, JudgeStatus.AC)  # type: ignore[attr-defined]

    def fake_diagnose(
        problem: object, submission: object, judged: JudgeResult
    ) -> DiagnosisReport:
        return DiagnosisReport(submission.id, "problem-1", None)  # type: ignore[attr-defined]

    monkeypatch.setattr("services.teacher_workflow.judge_submission", fake_judge)  # type: ignore[attr-defined]
    monkeypatch.setattr("services.teacher_workflow.diagnose_submission", fake_diagnose)  # type: ignore[attr-defined]

    result = analyze_class(
        make_problem(),
        standard_source_code="int main() {}",
        students=(
            StudentSource("失败学生", "bad.cpp", "int main() {}"),
            StudentSource("正常学生", "ok.cpp", "int main() {}"),
        ),
    )

    assert result.students[0].error_message is not None
    assert "isolated failure" in result.students[0].error_message
    assert result.students[1].judge_result is not None
