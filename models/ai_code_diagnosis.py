"""Structured, explicitly non-deterministic AI code diagnosis results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.exceptions import ModelValidationError


class AIConclusion(str, Enum):
    LIKELY_CORRECT = "likely_correct"
    LIKELY_INCORRECT = "likely_incorrect"
    UNCERTAIN = "uncertain"


ALLOWED_DIAGNOSIS_CATEGORIES = frozenset(
    {
        "syntax_error",
        "compile_risk",
        "logic_error",
        "boundary_error",
        "input_error",
        "output_format_error",
        "complexity_risk",
        "data_type_error",
        "array_index_error",
        "uncertain",
    }
)


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelValidationError(f"{field_name} must be a non-empty string")


def _text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    try:
        result = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ModelValidationError(f"{field_name} must be iterable") from exc
    if not result or not all(isinstance(item, str) and item.strip() for item in result):
        raise ModelValidationError(f"{field_name} must contain non-empty strings")
    return result


@dataclass(frozen=True, slots=True)
class CodeEvidence:
    line: int | None
    code: str
    explanation: str

    def __post_init__(self) -> None:
        if self.line is not None and (
            isinstance(self.line, bool) or not isinstance(self.line, int) or self.line <= 0
        ):
            raise ModelValidationError("CodeEvidence.line must be positive or None")
        if not isinstance(self.code, str):
            raise ModelValidationError("CodeEvidence.code must be a string")
        _required_text(self.explanation, "CodeEvidence.explanation")


@dataclass(frozen=True, slots=True)
class SampleAnalysis:
    sample_index: int
    analysis: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.sample_index, bool)
            or not isinstance(self.sample_index, int)
            or self.sample_index <= 0
        ):
            raise ModelValidationError("SampleAnalysis.sample_index must be positive")
        _required_text(self.analysis, "SampleAnalysis.analysis")


@dataclass(frozen=True, slots=True)
class AICodeDiagnosis:
    conclusion: AIConclusion
    summary: str
    categories: tuple[str, ...]
    root_cause: str
    evidence: tuple[CodeEvidence, ...]
    sample_analysis: tuple[SampleAnalysis, ...]
    suggestions: tuple[str, ...]
    teacher_feedback: str
    student_feedback: str
    confidence: float
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.conclusion, AIConclusion):
            raise ModelValidationError("AICodeDiagnosis.conclusion is invalid")
        for field_name in (
            "summary",
            "root_cause",
            "teacher_feedback",
            "student_feedback",
        ):
            _required_text(getattr(self, field_name), f"AICodeDiagnosis.{field_name}")
        categories = _text_tuple(self.categories, "AICodeDiagnosis.categories")
        if not set(categories) <= ALLOWED_DIAGNOSIS_CATEGORIES:
            raise ModelValidationError("AICodeDiagnosis.categories contains invalid values")
        suggestions = _text_tuple(self.suggestions, "AICodeDiagnosis.suggestions")
        limitations = _text_tuple(self.limitations, "AICodeDiagnosis.limitations")
        try:
            evidence = tuple(self.evidence)
            sample_analysis = tuple(self.sample_analysis)
        except TypeError as exc:
            raise ModelValidationError("diagnosis detail fields must be iterable") from exc
        if not all(isinstance(item, CodeEvidence) for item in evidence):
            raise ModelValidationError("evidence must contain CodeEvidence values")
        if not all(isinstance(item, SampleAnalysis) for item in sample_analysis):
            raise ModelValidationError("sample_analysis must contain SampleAnalysis values")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0 <= self.confidence <= 1
        ):
            raise ModelValidationError("AICodeDiagnosis.confidence must be between 0 and 1")
        object.__setattr__(self, "categories", categories)
        object.__setattr__(self, "suggestions", suggestions)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "sample_analysis", sample_analysis)
        object.__setattr__(self, "confidence", float(self.confidence))
