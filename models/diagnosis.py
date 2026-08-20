"""Future-facing diagnosis domain model (no AI behavior)."""

from dataclasses import dataclass

from core.exceptions import ModelValidationError


@dataclass(frozen=True, slots=True)
class Diagnosis:
    """Structured explanation of an observed submission issue."""

    category: str
    summary: str
    detail: str
    confidence: float
    related_lines: tuple[int, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("category", "summary", "detail"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"Diagnosis.{field_name} must be a non-empty string"
                )
        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, (int, float)
        ):
            raise ModelValidationError("Diagnosis.confidence must be a number")
        if not 0 <= self.confidence <= 1:
            raise ModelValidationError("Diagnosis.confidence must be between 0 and 1")

        try:
            related_lines = tuple(self.related_lines)
            evidence = tuple(self.evidence)
        except TypeError as exc:
            raise ModelValidationError(
                "Diagnosis.related_lines and evidence must be iterable"
            ) from exc
        if not all(
            isinstance(line, int) and not isinstance(line, bool) and line > 0
            for line in related_lines
        ):
            raise ModelValidationError(
                "Diagnosis.related_lines must contain positive integers"
            )
        if not all(isinstance(item, str) for item in evidence):
            raise ModelValidationError("Diagnosis.evidence must contain strings")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "related_lines", related_lines)
        object.__setattr__(self, "evidence", evidence)
