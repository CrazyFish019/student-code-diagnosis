"""Data transferred between the teacher workflow service and local UI."""

from __future__ import annotations

from dataclasses import dataclass

from core.exceptions import ModelValidationError
from models.diagnosis_report import DiagnosisReport
from models.explanation_result import ExplanationResult
from models.judge_result import JudgeResult


@dataclass(frozen=True, slots=True)
class StudentSource:
    student_name: str
    filename: str
    source_code: str

    def __post_init__(self) -> None:
        for field_name in ("student_name", "filename"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"StudentSource.{field_name} must be a non-empty string"
                )
        if not isinstance(self.source_code, str) or not self.source_code.strip():
            raise ModelValidationError(
                "StudentSource.source_code must be a non-empty string"
            )


@dataclass(frozen=True, slots=True)
class StudentAnalysis:
    student_name: str
    submission_id: str
    judge_result: JudgeResult | None
    diagnosis_report: DiagnosisReport | None
    explanation_result: ExplanationResult | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("student_name", "submission_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"StudentAnalysis.{field_name} must be a non-empty string"
                )
        if self.error_message is None:
            if self.judge_result is None or self.diagnosis_report is None:
                raise ModelValidationError(
                    "Successful StudentAnalysis requires judge and diagnosis results"
                )
        else:
            if not isinstance(self.error_message, str) or not self.error_message.strip():
                raise ModelValidationError(
                    "StudentAnalysis.error_message must be non-empty or None"
                )
            if self.judge_result is not None or self.diagnosis_report is not None:
                raise ModelValidationError(
                    "Failed StudentAnalysis cannot contain partial domain results"
                )


@dataclass(frozen=True, slots=True)
class ClassAnalysisResult:
    problem_id: str
    standard_judge_result: JudgeResult
    students: tuple[StudentAnalysis, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.problem_id, str) or not self.problem_id.strip():
            raise ModelValidationError(
                "ClassAnalysisResult.problem_id must be a non-empty string"
            )
        if not isinstance(self.standard_judge_result, JudgeResult):
            raise ModelValidationError(
                "ClassAnalysisResult.standard_judge_result must be a JudgeResult"
            )
        try:
            students = tuple(self.students)
        except TypeError as exc:
            raise ModelValidationError(
                "ClassAnalysisResult.students must be iterable"
            ) from exc
        if not all(isinstance(item, StudentAnalysis) for item in students):
            raise ModelValidationError(
                "ClassAnalysisResult.students must contain StudentAnalysis values"
            )
        object.__setattr__(self, "students", students)
