import pytest

from core.exceptions import ModelValidationError
from models import TestCase as DomainTestCase


def test_testcase_creation_preserves_real_newlines() -> None:
    testcase = DomainTestCase("case-1", "1 2\n3 4\n", "3\n7\n")

    assert testcase.input_data == "1 2\n3 4\n"
    assert testcase.expected_output.splitlines() == ["3", "7"]
    assert "\\n" not in testcase.input_data


@pytest.mark.parametrize("empty_id", ["", "   "])
def test_testcase_rejects_empty_id(empty_id: str) -> None:
    with pytest.raises(ModelValidationError, match="id"):
        DomainTestCase(empty_id, "", "")


def test_testcase_is_immutable() -> None:
    testcase = DomainTestCase("case-1", "", "")

    with pytest.raises(AttributeError):
        testcase.id = "changed"  # type: ignore[misc]
