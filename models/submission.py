"""Student submission domain model."""

from dataclasses import dataclass
from datetime import datetime

from core.exceptions import ModelValidationError


@dataclass(frozen=True, slots=True)
class Submission:
    """A snapshot of source code submitted by one student."""

    id: str
    problem_id: str
    student_id: str
    student_name: str
    language: str
    source_code: str
    submitted_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("id", "problem_id", "student_id", "student_name"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"Submission.{field_name} must be a non-empty string"
                )
        if self.language != "cpp":
            raise ModelValidationError("Submission.language must be 'cpp'")
        if not isinstance(self.source_code, str):
            raise ModelValidationError("Submission.source_code must be a string")
        if not isinstance(self.submitted_at, datetime):
            raise ModelValidationError("Submission.submitted_at must be a datetime")
