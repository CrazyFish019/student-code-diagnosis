import pytest

from models import DiagnosisReport
from services import generate_explanation_placeholder


def test_placeholder_accepts_diagnosis_report_and_returns_none() -> None:
    report = DiagnosisReport.from_fields(
        submission_id="submission-1",
        problem_id="problem-1",
        category="boundary_error",
        summary="疑似边界条件处理错误",
        detail="边界测试点失败。",
        confidence=0.8,
        evidence=("最小数据失败", "最大数据失败"),
    )

    assert generate_explanation_placeholder(report) is None
    assert report.category == "boundary_error"
    assert report.confidence == 0.8


def test_placeholder_rejects_direct_judge_or_other_values() -> None:
    with pytest.raises(TypeError, match="DiagnosisReport"):
        generate_explanation_placeholder(object())  # type: ignore[arg-type]
