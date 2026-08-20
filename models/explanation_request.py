"""Structured input for the platform-neutral explanation layer."""

from dataclasses import dataclass

from core.exceptions import ModelValidationError


@dataclass(frozen=True, slots=True)
class ExplanationRequest:
    """The limited facts permitted to enter an explanation provider prompt."""

    submission_id: str
    problem_id: str
    problem_title: str
    diagnosis_category: str
    diagnosis_summary: str
    evidence: tuple[str, ...]
    source_code: str

    def __post_init__(self) -> None:
        for field_name in (
            "submission_id",
            "problem_id",
            "problem_title",
            "diagnosis_category",
            "diagnosis_summary",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"ExplanationRequest.{field_name} must be a non-empty string"
                )
        if not isinstance(self.source_code, str):
            raise ModelValidationError("ExplanationRequest.source_code must be a string")
        try:
            evidence = tuple(self.evidence)
        except TypeError as exc:
            raise ModelValidationError(
                "ExplanationRequest.evidence must be iterable"
            ) from exc
        if not all(isinstance(item, str) and item.strip() for item in evidence):
            raise ModelValidationError(
                "ExplanationRequest.evidence must contain non-empty strings"
            )
        object.__setattr__(self, "evidence", evidence)
