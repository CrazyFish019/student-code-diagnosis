"""Problem statements imported from a supported online judge."""

from __future__ import annotations

from dataclasses import dataclass

from core.exceptions import ModelValidationError


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelValidationError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ProblemExample:
    input_data: str
    expected_output: str

    def __post_init__(self) -> None:
        if not isinstance(self.input_data, str) or not isinstance(
            self.expected_output, str
        ):
            raise ModelValidationError("ProblemExample fields must be strings")


@dataclass(frozen=True, slots=True)
class ImportedProblem:
    source_url: str
    oj_name: str
    external_problem_id: str
    title: str
    description: str
    input_description: str
    output_description: str
    hint: str
    time_limit_ms: int
    memory_limit_mb: int
    examples: tuple[ProblemExample, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("source_url", "oj_name", "external_problem_id", "title"):
            _required_text(getattr(self, field_name), f"ImportedProblem.{field_name}")
        for field_name in (
            "description",
            "input_description",
            "output_description",
            "hint",
        ):
            if not isinstance(getattr(self, field_name), str):
                raise ModelValidationError(
                    f"ImportedProblem.{field_name} must be a string"
                )
        for field_name in ("time_limit_ms", "memory_limit_mb"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ModelValidationError(
                    f"ImportedProblem.{field_name} must be a positive integer"
                )
        try:
            examples = tuple(self.examples)
        except TypeError as exc:
            raise ModelValidationError("ImportedProblem.examples must be iterable") from exc
        if not all(isinstance(item, ProblemExample) for item in examples):
            raise ModelValidationError(
                "ImportedProblem.examples must contain ProblemExample values"
            )
        object.__setattr__(self, "examples", examples)
