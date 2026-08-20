"""Pure conversion of domain/service results into teacher-facing view data."""

from __future__ import annotations

from models.explanation_result import ExplanationStatus
from models.workbench import ClassAnalysisResult, StudentAnalysis
from services.result_query import StudentResultRow
from services.teacher_workflow import TeacherWorkflowError
from ui.file_parsers import UIInputError

_DIAGNOSIS_LABELS = {
    "compile_error": "编译错误",
    "runtime_error": "运行时错误",
    "performance_issue": "性能问题",
    "output_format_error": "输出格式问题",
    "boundary_error": "边界问题",
}


def diagnosis_label(category: str | None) -> str:
    if category is None:
        return "-"
    return _DIAGNOSIS_LABELS.get(category, category)


def build_summary_rows(result: ClassAnalysisResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for student in result.students:
        if student.error_message is not None:
            rows.append(
                {
                    "学生": student.student_name,
                    "状态": "处理失败",
                    "通过": "-",
                    "诊断": "-",
                }
            )
            continue
        assert student.judge_result is not None
        assert student.diagnosis_report is not None
        judged = student.judge_result
        rows.append(
            {
                "学生": student.student_name,
                "状态": judged.final_status.value,
                "通过": f"{judged.passed_count}/{judged.total_count}",
                "诊断": diagnosis_label(student.diagnosis_report.category),
            }
        )
    return rows


def build_status_counts(result: ClassAnalysisResult) -> dict[str, int]:
    counts: dict[str, int] = {"TOTAL": len(result.students)}
    for student in result.students:
        status = (
            "FAILED"
            if student.judge_result is None
            else student.judge_result.final_status.value
        )
        counts[status] = counts.get(status, 0) + 1
    return counts


def explanation_text(student: StudentAnalysis) -> tuple[str | None, str | None]:
    result = student.explanation_result
    if (
        result is None
        or result.status is not ExplanationStatus.SUCCESS
        or result.explanation is None
    ):
        return None, None
    return result.explanation.teacher_explanation, result.explanation.student_explanation


def exception_to_user_message(exc: Exception) -> str:
    if isinstance(exc, (UIInputError, TeacherWorkflowError)):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        return "编译器或文件不可用，请检查本地配置。"
    if isinstance(exc, ValueError):
        return f"输入数据无效：{exc}"
    return "处理失败，请检查输入文件和本地编译器配置。"


def result_row_to_view(row: StudentResultRow) -> dict[str, object]:
    return {
        "学生姓名": row.student_name,
        "状态": row.status,
        "通过数": row.passed_count,
        "总测试点": row.total_count,
        "通过率": f"{row.pass_rate:.0%}",
        "主要诊断": diagnosis_label(row.diagnosis_category),
        "AI解释状态": row.explanation_status,
    }
