import pytest

from core.exceptions import ModelValidationError
from models.imported_problem import ImportedProblem, ProblemExample


def make_problem(**overrides) -> ImportedProblem:
    values = {
        "source_url": "https://www.vesibay.cn/problem/AC743",
        "oj_name": "Vesibay",
        "external_problem_id": "AC743",
        "title": "数组中的行",
        "description": "题目描述",
        "input_description": "输入描述",
        "output_description": "输出描述",
        "hint": "",
        "time_limit_ms": 1000,
        "memory_limit_mb": 256,
        "examples": [ProblemExample("1\n", "2\n")],
    }
    values.update(overrides)
    return ImportedProblem(**values)


def test_imported_problem_normalizes_examples_to_tuple() -> None:
    problem = make_problem()

    assert isinstance(problem.examples, tuple)
    assert problem.examples[0].input_data == "1\n"


@pytest.mark.parametrize("field", ["source_url", "oj_name", "external_problem_id", "title"])
def test_imported_problem_rejects_empty_identity(field) -> None:
    with pytest.raises(ModelValidationError):
        make_problem(**{field: " "})


def test_imported_problem_rejects_invalid_limits() -> None:
    with pytest.raises(ModelValidationError):
        make_problem(time_limit_ms=0)
