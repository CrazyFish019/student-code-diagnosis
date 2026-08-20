from dataclasses import FrozenInstanceError

import pytest

from core.exceptions import ModelValidationError
from models import (
    AIExplanation,
    ExplanationRequest,
    ExplanationResult,
    ExplanationStatus,
)


def make_explanation() -> AIExplanation:
    return AIExplanation(
        submission_id="submission-1",
        problem_id="problem-1",
        source_diagnosis_category="boundary_error",
        teacher_explanation="teacher",
        student_explanation="student",
        confidence_note="confidence",
    )


def test_explanation_request_converts_evidence_to_tuple() -> None:
    request = ExplanationRequest(
        submission_id="submission-1",
        problem_id="problem-1",
        problem_title="A+B",
        diagnosis_category="boundary_error",
        diagnosis_summary="Boundary issue",
        evidence=["small failed", "large failed"],  # type: ignore[arg-type]
        source_code="int main() {}\n",
    )

    assert request.evidence == ("small failed", "large failed")


def test_explanation_result_success_invariants() -> None:
    result = ExplanationResult(ExplanationStatus.SUCCESS, make_explanation())

    assert result.explanation is not None
    assert result.error_message is None


def test_explanation_result_failure_and_unavailable_states() -> None:
    failed = ExplanationResult(
        ExplanationStatus.FAILED,
        error_message="provider failed",
    )
    unavailable = ExplanationResult(ExplanationStatus.NOT_AVAILABLE)

    assert failed.explanation is None
    assert unavailable.explanation is None
    assert unavailable.error_message is None


@pytest.mark.parametrize(
    "result_factory",
    [
        lambda: ExplanationResult(ExplanationStatus.SUCCESS),
        lambda: ExplanationResult(
            ExplanationStatus.SUCCESS,
            make_explanation(),
            "unexpected error",
        ),
        lambda: ExplanationResult(ExplanationStatus.FAILED),
        lambda: ExplanationResult(
            ExplanationStatus.NOT_AVAILABLE,
            make_explanation(),
        ),
    ],
)
def test_explanation_result_rejects_contradictory_states(result_factory: object) -> None:
    with pytest.raises(ModelValidationError):
        result_factory()  # type: ignore[operator]


def test_explanation_result_is_immutable() -> None:
    result = ExplanationResult(ExplanationStatus.NOT_AVAILABLE)

    with pytest.raises(FrozenInstanceError):
        result.status = ExplanationStatus.FAILED  # type: ignore[misc]
