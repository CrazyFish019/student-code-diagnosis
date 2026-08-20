"""Future-facing teaching explanation model with no AI behavior."""

from dataclasses import dataclass

from core.exceptions import ModelValidationError


@dataclass(frozen=True, slots=True)
class AIExplanation:
    """Human-facing explanations derived from a rule diagnosis.

    This value object stores explanation-layer output only. It has no reference
    to, and cannot mutate, either DiagnosisReport or JudgeResult.
    """

    submission_id: str
    problem_id: str
    source_diagnosis_category: str | None = None
    teacher_explanation: str | None = None
    student_explanation: str | None = None
    confidence_note: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("submission_id", "problem_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"AIExplanation.{field_name} must be a non-empty string"
                )

        for field_name in (
            "source_diagnosis_category",
            "teacher_explanation",
            "student_explanation",
            "confidence_note",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ModelValidationError(
                    f"AIExplanation.{field_name} must be a non-empty string or None"
                )
