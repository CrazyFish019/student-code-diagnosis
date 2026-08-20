"""Database-neutral read/write records for local task history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.exceptions import ModelValidationError


def _non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelValidationError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class TaskRecord:
    id: str
    title: str
    problem_id: str
    created_at: datetime
    student_count: int

    def __post_init__(self) -> None:
        _non_empty(self.id, "TaskRecord.id")
        _non_empty(self.title, "TaskRecord.title")
        _non_empty(self.problem_id, "TaskRecord.problem_id")
        if not isinstance(self.created_at, datetime):
            raise ModelValidationError("TaskRecord.created_at must be a datetime")
        if (
            isinstance(self.student_count, bool)
            or not isinstance(self.student_count, int)
            or self.student_count < 0
        ):
            raise ModelValidationError(
                "TaskRecord.student_count must be a non-negative integer"
            )


@dataclass(frozen=True, slots=True)
class SubmissionRecord:
    id: str
    task_id: str
    student_name: str
    status: str
    passed_count: int
    total_count: int
    source_file_path: str
    result_file_path: str
    error_message: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "id",
            "task_id",
            "student_name",
            "status",
            "source_file_path",
            "result_file_path",
        ):
            _non_empty(getattr(self, field_name), f"SubmissionRecord.{field_name}")
        for field_name in ("passed_count", "total_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ModelValidationError(
                    f"SubmissionRecord.{field_name} must be a non-negative integer"
                )
        if self.passed_count > self.total_count:
            raise ModelValidationError("passed_count cannot exceed total_count")
        if self.error_message is not None:
            _non_empty(self.error_message, "SubmissionRecord.error_message")


@dataclass(frozen=True, slots=True)
class DiagnosisRecord:
    id: int | None
    submission_id: str
    category: str | None
    summary: str
    detail: str
    confidence: float
    evidence: tuple[str, ...]
    related_lines: tuple[int, ...]
    secondary_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _non_empty(self.submission_id, "DiagnosisRecord.submission_id")
        if self.category is not None:
            _non_empty(self.category, "DiagnosisRecord.category")
        if not isinstance(self.summary, str) or not isinstance(self.detail, str):
            raise ModelValidationError("DiagnosisRecord text fields must be strings")
        if not isinstance(self.confidence, (int, float)) or isinstance(
            self.confidence, bool
        ) or not 0 <= self.confidence <= 1:
            raise ModelValidationError("DiagnosisRecord.confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", float(self.confidence))
        for field_name in ("evidence", "related_lines", "secondary_evidence"):
            try:
                object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
            except TypeError as exc:
                raise ModelValidationError(
                    f"DiagnosisRecord.{field_name} must be iterable"
                ) from exc


@dataclass(frozen=True, slots=True)
class ExplanationRecord:
    id: int | None
    submission_id: str
    status: str
    teacher_explanation: str | None
    student_explanation: str | None
    confidence_note: str | None
    error_message: str | None = None

    def __post_init__(self) -> None:
        _non_empty(self.submission_id, "ExplanationRecord.submission_id")
        _non_empty(self.status, "ExplanationRecord.status")
        for field_name in (
            "teacher_explanation",
            "student_explanation",
            "confidence_note",
            "error_message",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _non_empty(value, f"ExplanationRecord.{field_name}")


@dataclass(frozen=True, slots=True)
class HistoricalStudent:
    submission: SubmissionRecord
    diagnosis: DiagnosisRecord | None
    explanation: ExplanationRecord | None
    result_data: dict[str, object]


@dataclass(frozen=True, slots=True)
class HistoricalTask:
    task: TaskRecord
    students: tuple[HistoricalStudent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "students", tuple(self.students))
