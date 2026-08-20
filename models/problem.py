"""Problem domain model."""

from dataclasses import dataclass
from typing import Iterable

from core.exceptions import ModelValidationError
from models.testcase import TestCase


@dataclass(frozen=True, slots=True)
class Problem:
    """An immutable programming problem definition."""

    id: str
    title: str
    description: str
    time_limit_ms: int
    memory_limit_mb: int
    test_cases: tuple[TestCase, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ModelValidationError("Problem.id must be a non-empty string")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ModelValidationError("Problem.title must be a non-empty string")
        if not isinstance(self.description, str):
            raise ModelValidationError("Problem.description must be a string")
        if isinstance(self.time_limit_ms, bool) or not isinstance(self.time_limit_ms, int):
            raise ModelValidationError("Problem.time_limit_ms must be an integer")
        if self.time_limit_ms <= 0:
            raise ModelValidationError("Problem.time_limit_ms must be greater than 0")
        if isinstance(self.memory_limit_mb, bool) or not isinstance(self.memory_limit_mb, int):
            raise ModelValidationError("Problem.memory_limit_mb must be an integer")
        if self.memory_limit_mb <= 0:
            raise ModelValidationError("Problem.memory_limit_mb must be greater than 0")

        try:
            test_cases = tuple(self.test_cases)
        except TypeError as exc:
            raise ModelValidationError("Problem.test_cases must be iterable") from exc
        if not all(isinstance(test_case, TestCase) for test_case in test_cases):
            raise ModelValidationError("Problem.test_cases must contain only TestCase values")
        if len({test_case.id for test_case in test_cases}) != len(test_cases):
            raise ModelValidationError("Problem.test_cases must have unique ids")
        object.__setattr__(self, "test_cases", test_cases)

    @classmethod
    def from_test_cases(
        cls,
        *,
        id: str,
        title: str,
        description: str,
        time_limit_ms: int,
        memory_limit_mb: int,
        test_cases: Iterable[TestCase],
    ) -> "Problem":
        """Construct a problem from any iterable while storing an immutable tuple."""
        return cls(
            id=id,
            title=title,
            description=description,
            time_limit_ms=time_limit_ms,
            memory_limit_mb=memory_limit_mb,
            test_cases=tuple(test_cases),
        )
