"""Application service orchestrating one local teacher diagnosis task."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from models.explanation_result import ExplanationResult
from models.judge_result import JudgeStatus
from models.problem import Problem
from models.submission import Submission
from models.workbench import ClassAnalysisResult, StudentAnalysis, StudentSource
from services.ai_explanation_service import generate_explanation
from services.ai_provider import AIProvider
from services.diagnosis_engine import diagnose_submission
from services.judge_engine import judge_submission

ProgressCallback = Callable[[int, int, str], None]


class TeacherWorkflowError(RuntimeError):
    """A task-level error safe for conversion into a teacher-facing message."""


def _submission(
    *,
    submission_id: str,
    problem: Problem,
    student_id: str,
    student_name: str,
    source_code: str,
) -> Submission:
    return Submission(
        id=submission_id,
        problem_id=problem.id,
        student_id=student_id,
        student_name=student_name,
        language="cpp",
        source_code=source_code,
        submitted_at=datetime.now(timezone.utc),
    )


def analyze_class(
    problem: Problem,
    *,
    standard_source_code: str,
    students: Sequence[StudentSource],
    compiler: str | Path = "g++",
    compile_timeout_ms: int = 10_000,
    explanation_provider: AIProvider | None = None,
    temp_root: str | Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ClassAnalysisResult:
    """Validate the standard program, then analyze every student independently."""
    if not isinstance(problem, Problem):
        raise TypeError("problem must be a Problem")
    if not isinstance(standard_source_code, str) or not standard_source_code.strip():
        raise TeacherWorkflowError("标准程序为空，请上传有效的 C++ 文件。")
    student_sources = tuple(students)
    if not student_sources:
        raise TeacherWorkflowError("没有找到学生 C++ 文件。")
    if not all(isinstance(item, StudentSource) for item in student_sources):
        raise TypeError("students must contain StudentSource values")

    standard_submission = _submission(
        submission_id=f"standard-{problem.id}",
        problem=problem,
        student_id="__standard__",
        student_name="标准程序",
        source_code=standard_source_code,
    )
    standard_result = judge_submission(
        problem,
        standard_submission,
        compiler=compiler,
        compile_timeout_ms=compile_timeout_ms,
        temp_root=temp_root,
    )
    if standard_result.final_status is not JudgeStatus.AC:
        if standard_result.final_status is JudgeStatus.SYSTEM_ERROR:
            raise TeacherWorkflowError(
                "编译器不可用或判题基础设施异常，请检查 g++ 路径和配置。"
            )
        raise TeacherWorkflowError(
            f"标准程序未通过测试，当前状态为 {standard_result.final_status.value}。"
        )

    analyses: list[StudentAnalysis] = []
    total = len(student_sources)
    for index, student in enumerate(student_sources, start=1):
        submission_id = f"student-{index}-{problem.id}"
        try:
            submission = _submission(
                submission_id=submission_id,
                problem=problem,
                student_id=f"student-{index}",
                student_name=student.student_name,
                source_code=student.source_code,
            )
            judged = judge_submission(
                problem,
                submission,
                compiler=compiler,
                compile_timeout_ms=compile_timeout_ms,
                temp_root=temp_root,
            )
            diagnosis = diagnose_submission(problem, submission, judged)
            explanation: ExplanationResult | None = None
            if explanation_provider is not None:
                explanation = generate_explanation(
                    problem,
                    submission,
                    diagnosis,
                    explanation_provider,
                )
            analyses.append(
                StudentAnalysis(
                    student_name=student.student_name,
                    submission_id=submission_id,
                    judge_result=judged,
                    diagnosis_report=diagnosis,
                    explanation_result=explanation,
                )
            )
        except Exception as exc:
            analyses.append(
                StudentAnalysis(
                    student_name=student.student_name,
                    submission_id=submission_id,
                    judge_result=None,
                    diagnosis_report=None,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            )
        if progress_callback is not None:
            progress_callback(index, total, student.student_name)

    return ClassAnalysisResult(
        problem_id=problem.id,
        standard_judge_result=standard_result,
        students=tuple(analyses),
    )
