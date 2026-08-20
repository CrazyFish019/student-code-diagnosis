from dataclasses import FrozenInstanceError

import pytest

from core.exceptions import ModelValidationError
from models import AIExplanation


def test_ai_explanation_normal_creation() -> None:
    explanation = AIExplanation(
        submission_id="submission-1",
        problem_id="problem-1",
        source_diagnosis_category="boundary_error",
        teacher_explanation="该学生算法主体正确，但边界条件处理不足。",
        student_explanation="你的代码大部分情况正确，请检查最小和最大数据。",
        confidence_note="基于规则诊断生成，非直接代码证明。",
    )

    assert explanation.submission_id == "submission-1"
    assert explanation.source_diagnosis_category == "boundary_error"
    assert "边界" in (explanation.teacher_explanation or "")


@pytest.mark.parametrize("submission_id", ["", "   "])
def test_ai_explanation_rejects_empty_submission_id(submission_id: str) -> None:
    with pytest.raises(ModelValidationError, match="submission_id"):
        AIExplanation(submission_id=submission_id, problem_id="problem-1")


@pytest.mark.parametrize("problem_id", ["", "\t"])
def test_ai_explanation_rejects_empty_problem_id(problem_id: str) -> None:
    with pytest.raises(ModelValidationError, match="problem_id"):
        AIExplanation(submission_id="submission-1", problem_id=problem_id)


@pytest.mark.parametrize(
    "field_name",
    [
        "source_diagnosis_category",
        "teacher_explanation",
        "student_explanation",
        "confidence_note",
    ],
)
def test_ai_explanation_rejects_blank_optional_string(field_name: str) -> None:
    with pytest.raises(ModelValidationError, match=field_name):
        AIExplanation(
            submission_id="submission-1",
            problem_id="problem-1",
            **{field_name: "   "},
        )


def test_ai_explanation_accepts_none_optional_fields() -> None:
    explanation = AIExplanation("submission-1", "problem-1")

    assert explanation.source_diagnosis_category is None
    assert explanation.teacher_explanation is None
    assert explanation.student_explanation is None
    assert explanation.confidence_note is None


def test_ai_explanation_is_immutable() -> None:
    explanation = AIExplanation("submission-1", "problem-1")

    with pytest.raises(FrozenInstanceError):
        explanation.teacher_explanation = "changed"  # type: ignore[misc]
