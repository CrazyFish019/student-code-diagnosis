"""Test case domain model."""

from dataclasses import dataclass

from core.exceptions import ModelValidationError


@dataclass(frozen=True, slots=True)
class TestCase:
    """Input and expected output for one judging test case."""

    id: str
    input_data: str
    expected_output: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ModelValidationError("TestCase.id must be a non-empty string")
        if not isinstance(self.input_data, str):
            raise ModelValidationError("TestCase.input_data must be a string")
        if not isinstance(self.expected_output, str):
            raise ModelValidationError("TestCase.expected_output must be a string")
