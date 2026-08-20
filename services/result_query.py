"""Teacher-facing result projection, sorting, filtering, and statistics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from models.history import HistoricalStudent, HistoricalTask
from models.workbench import ClassAnalysisResult


class ResultSort(str, Enum):
    ATTENTION = "问题优先"
    NAME = "按姓名"
    STATUS = "按状态"
    PASS_RATE = "按通过率"


_STATUS_SEVERITY = {
    "SYSTEM_ERROR": 0,
    "TLE": 1,
    "RE": 2,
    "CE": 3,
    "WA": 4,
    "PROCESSING_ERROR": 5,
    "AC": 6,
}


@dataclass(frozen=True, slots=True)
class StudentResultRow:
    submission_id: str
    student_name: str
    status: str
    passed_count: int
    total_count: int
    diagnosis_category: str | None
    explanation_status: str

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total_count if self.total_count else 0.0


def project_historical_results(task: HistoricalTask) -> tuple[StudentResultRow, ...]:
    return tuple(_project_student(student) for student in task.students)


def project_current_results(result: ClassAnalysisResult) -> tuple[StudentResultRow, ...]:
    rows: list[StudentResultRow] = []
    for student in result.students:
        judge = student.judge_result
        diagnosis = student.diagnosis_report
        explanation = student.explanation_result
        rows.append(
            StudentResultRow(
                submission_id=student.submission_id,
                student_name=student.student_name,
                status=judge.final_status.value if judge else "PROCESSING_ERROR",
                passed_count=judge.passed_count if judge else 0,
                total_count=judge.total_count if judge else 0,
                diagnosis_category=diagnosis.category if diagnosis else None,
                explanation_status=(
                    explanation.status.value if explanation else "NOT_AVAILABLE"
                ),
            )
        )
    return tuple(rows)


def query_results(
    rows: Iterable[StudentResultRow],
    *,
    sort_by: ResultSort = ResultSort.ATTENTION,
    status: str | None = None,
    diagnosis: str | None = None,
) -> tuple[StudentResultRow, ...]:
    filtered = [
        row
        for row in rows
        if (status is None or row.status == status)
        and (diagnosis is None or row.diagnosis_category == diagnosis)
    ]
    return tuple(sorted(filtered, key=lambda row: _sort_key(row, sort_by)))


def result_statistics(rows: Iterable[StudentResultRow]) -> dict[str, object]:
    values = tuple(rows)
    statistics: dict[str, object] = {"TOTAL": len(values)}
    for row in values:
        statistics[row.status] = int(statistics.get(row.status, 0)) + 1
    diagnosis_counts: dict[str, int] = {}
    for row in values:
        if row.diagnosis_category:
            diagnosis_counts[row.diagnosis_category] = (
                diagnosis_counts.get(row.diagnosis_category, 0) + 1
            )
    statistics["DIAGNOSIS"] = diagnosis_counts
    return statistics


def _project_student(student: HistoricalStudent) -> StudentResultRow:
    submission = student.submission
    return StudentResultRow(
        submission_id=submission.id,
        student_name=submission.student_name,
        status=submission.status,
        passed_count=submission.passed_count,
        total_count=submission.total_count,
        diagnosis_category=(student.diagnosis.category if student.diagnosis else None),
        explanation_status=(
            student.explanation.status if student.explanation else "NOT_AVAILABLE"
        ),
    )


def _sort_key(row: StudentResultRow, sort_by: ResultSort) -> tuple[object, ...]:
    severity = _STATUS_SEVERITY.get(row.status, 5)
    if sort_by is ResultSort.NAME:
        return (row.student_name.casefold(), severity)
    if sort_by is ResultSort.STATUS:
        return (severity, row.pass_rate, row.student_name.casefold())
    if sort_by is ResultSort.PASS_RATE:
        return (row.pass_rate, severity, row.student_name.casefold())
    return (
        row.status == "AC",
        row.pass_rate,
        severity,
        row.student_name.casefold(),
    )
