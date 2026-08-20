from dataclasses import FrozenInstanceError

import pytest

from core.exceptions import ModelValidationError
from models import Problem, TestCase as DomainTestCase


def make_problem(**overrides: object) -> Problem:
    values: dict[str, object] = {
        "id": "p-1",
        "title": "A + B",
        "description": "Add two integers.",
        "time_limit_ms": 1000,
        "memory_limit_mb": 256,
        "test_cases": [DomainTestCase("case-1", "1 2\n", "3\n")],
    }
    values.update(overrides)
    return Problem(**values)  # type: ignore[arg-type]


def test_problem_creation_converts_test_cases_to_tuple() -> None:
    problem = make_problem()

    assert isinstance(problem.test_cases, tuple)
    assert problem.test_cases[0].id == "case-1"


@pytest.mark.parametrize("field_name", ["id", "title"])
def test_problem_rejects_empty_identity_fields(field_name: str) -> None:
    with pytest.raises(ModelValidationError, match=field_name):
        make_problem(**{field_name: " "})


@pytest.mark.parametrize("limit", [0, -1])
def test_problem_rejects_invalid_time_limit(limit: int) -> None:
    with pytest.raises(ModelValidationError, match="time_limit_ms"):
        make_problem(time_limit_ms=limit)


@pytest.mark.parametrize("limit", [0, -128])
def test_problem_rejects_invalid_memory_limit(limit: int) -> None:
    with pytest.raises(ModelValidationError, match="memory_limit_mb"):
        make_problem(memory_limit_mb=limit)


def test_problem_core_content_is_immutable() -> None:
    problem = make_problem()

    with pytest.raises(FrozenInstanceError):
        problem.title = "Changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        problem.test_cases.append(DomainTestCase("case-2", "", ""))  # type: ignore[attr-defined]


def test_problem_rejects_duplicate_testcase_ids() -> None:
    cases = [
        DomainTestCase("same", "1", "1"),
        DomainTestCase("same", "2", "2"),
    ]

    with pytest.raises(ModelValidationError, match="unique"):
        make_problem(test_cases=cases)
