from dataclasses import FrozenInstanceError

import pytest

from core.exceptions import ModelValidationError
from models import DiagnosisReport


def test_diagnosis_report_creation_and_flat_properties() -> None:
    report = DiagnosisReport.from_fields(
        submission_id="submission-1",
        problem_id="problem-1",
        category="compile_error",
        summary="程序无法编译",
        detail="编译器报告语法错误。",
        confidence=1.0,
        evidence=("line 3: expected ';'",),
        related_lines=(3,),
        secondary_evidence=("教师可先查看第 3 行。",),
    )

    assert report.category == "compile_error"
    assert report.confidence == 1.0
    assert report.evidence == ("line 3: expected ';'",)
    assert report.related_lines == (3,)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_diagnosis_report_rejects_invalid_confidence(confidence: float) -> None:
    with pytest.raises(ModelValidationError, match="confidence"):
        DiagnosisReport.from_fields(
            submission_id="submission-1",
            problem_id="problem-1",
            category="test",
            summary="summary",
            detail="detail",
            confidence=confidence,
        )


def test_diagnosis_report_is_immutable_and_uses_tuples() -> None:
    report = DiagnosisReport.from_fields(
        submission_id="submission-1",
        problem_id="problem-1",
        category="test",
        summary="summary",
        detail="detail",
        confidence=0.5,
        evidence=["evidence"],  # type: ignore[arg-type]
        secondary_evidence=["secondary"],  # type: ignore[arg-type]
    )

    assert report.evidence == ("evidence",)
    assert report.secondary_evidence == ("secondary",)
    with pytest.raises(FrozenInstanceError):
        report.problem_id = "changed"  # type: ignore[misc]


def test_report_can_explicitly_represent_no_reliable_diagnosis() -> None:
    report = DiagnosisReport("submission-1", "problem-1", None)

    assert report.category is None
    assert report.confidence == 0.0
    assert report.evidence == ()
