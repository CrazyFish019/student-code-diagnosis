from datetime import datetime, timezone

import pytest

from core.exceptions import ModelValidationError
from models import Submission


def make_submission(**overrides: object) -> Submission:
    values: dict[str, object] = {
        "id": "s-1",
        "problem_id": "p-1",
        "student_id": "stu-1",
        "student_name": "Alice",
        "language": "cpp",
        "source_code": "#include <iostream>\nint main() {}\n",
        "submitted_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return Submission(**values)  # type: ignore[arg-type]


def test_submission_creation() -> None:
    submission = make_submission()

    assert submission.language == "cpp"
    assert submission.source_code.endswith("\n")


@pytest.mark.parametrize("empty_id", ["", " "])
def test_submission_rejects_empty_id(empty_id: str) -> None:
    with pytest.raises(ModelValidationError, match="id"):
        make_submission(id=empty_id)


@pytest.mark.parametrize("language", ["c", "python", "CPP", ""])
def test_submission_rejects_non_cpp_language(language: str) -> None:
    with pytest.raises(ModelValidationError, match="language"):
        make_submission(language=language)
