from datetime import datetime, timezone

import json

from models import (
    DiagnosisReport,
    ExplanationStatus,
    Problem,
    Submission,
)
from services.ai_explanation_service import (
    build_explanation_prompt,
    build_explanation_request,
    generate_explanation,
)
from services.ai_provider import MockAIProvider


def make_problem() -> Problem:
    return Problem(
        id="problem-1",
        title="A+B 入门题",
        description="Add two integers.",
        time_limit_ms=1_000,
        memory_limit_mb=256,
        test_cases=(),
    )


def make_submission() -> Submission:
    return Submission(
        id="submission-1",
        problem_id="problem-1",
        student_id="student-1",
        student_name="Alice",
        language="cpp",
        source_code="int main() { return 0; }\n",
        submitted_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )


def make_report() -> DiagnosisReport:
    return DiagnosisReport.from_fields(
        submission_id="submission-1",
        problem_id="problem-1",
        category="boundary_error",
        summary="疑似边界条件处理错误",
        detail="最大数据失败。",
        confidence=0.8,
        evidence=("普通数据通过", "最大数据失败"),
    )


def test_normal_report_generates_correct_ai_explanation_fields() -> None:
    provider = MockAIProvider()

    result = generate_explanation(
        make_problem(), make_submission(), make_report(), provider
    )

    assert result.status is ExplanationStatus.SUCCESS
    assert result.error_message is None
    assert result.explanation is not None
    assert result.explanation.submission_id == "submission-1"
    assert result.explanation.problem_id == "problem-1"
    assert result.explanation.source_diagnosis_category == "boundary_error"
    assert result.explanation.teacher_explanation == "测试解释"
    assert result.explanation.student_explanation == "测试反馈"
    assert result.explanation.confidence_note == "测试说明"


def test_no_diagnosis_returns_not_available_without_provider_call() -> None:
    provider = MockAIProvider()
    report = DiagnosisReport("submission-1", "problem-1", None)

    result = generate_explanation(
        make_problem(), make_submission(), report, provider
    )

    assert result.status is ExplanationStatus.NOT_AVAILABLE
    assert result.explanation is None
    assert result.error_message is None
    assert provider.call_count == 0


def test_invalid_json_returns_failed_result() -> None:
    result = generate_explanation(
        make_problem(),
        make_submission(),
        make_report(),
        MockAIProvider("not valid JSON"),
    )

    assert result.status is ExplanationStatus.FAILED
    assert result.explanation is None
    assert "invalid JSON" in (result.error_message or "")


def test_missing_response_field_returns_failed_result() -> None:
    response = json.dumps(
        {
            "teacher_explanation": "teacher",
            "student_explanation": "student",
        }
    )

    result = generate_explanation(
        make_problem(), make_submission(), make_report(), MockAIProvider(response)
    )

    assert result.status is ExplanationStatus.FAILED
    assert "confidence_note" in (result.error_message or "")


def test_wrong_response_field_type_returns_failed_result() -> None:
    response = json.dumps(
        {
            "teacher_explanation": ["not", "a", "string"],
            "student_explanation": "student",
            "confidence_note": "note",
        }
    )

    result = generate_explanation(
        make_problem(), make_submission(), make_report(), MockAIProvider(response)
    )

    assert result.status is ExplanationStatus.FAILED
    assert "teacher_explanation" in (result.error_message or "")


def test_provider_exception_is_contained() -> None:
    class FailingProvider:
        def generate(self, prompt: str) -> str:
            raise RuntimeError("provider unavailable")

    report = make_report()
    result = generate_explanation(
        make_problem(), make_submission(), report, FailingProvider()
    )

    assert result.status is ExplanationStatus.FAILED
    assert "provider unavailable" in (result.error_message or "")
    assert report.category == "boundary_error"


def test_prompt_contains_only_structured_approved_context() -> None:
    request = build_explanation_request(
        make_problem(), make_submission(), make_report()
    )
    prompt = build_explanation_prompt(request)

    assert "A+B 入门题" in prompt
    assert "boundary_error" in prompt
    assert "普通数据通过" in prompt
    assert "int main() { return 0; }" in prompt
    assert "不要重新判断或更改错误类型" in prompt
    assert "诊断类别固定为 boundary_error" in prompt
    assert "teacher_explanation" in prompt


def test_provider_cannot_override_rule_diagnosis_category() -> None:
    response = json.dumps(
        {
            "teacher_explanation": "teacher",
            "student_explanation": "student",
            "confidence_note": "note",
            "source_diagnosis_category": "compile_error",
        }
    )

    result = generate_explanation(
        make_problem(), make_submission(), make_report(), MockAIProvider(response)
    )

    assert result.status is ExplanationStatus.SUCCESS
    assert result.explanation is not None
    assert result.explanation.source_diagnosis_category == "boundary_error"


def test_identity_mismatch_fails_without_calling_provider() -> None:
    provider = MockAIProvider()
    mismatched_report = DiagnosisReport.from_fields(
        submission_id="other-submission",
        problem_id="problem-1",
        category="boundary_error",
        summary="summary",
        detail="detail",
        confidence=0.8,
    )

    result = generate_explanation(
        make_problem(), make_submission(), mismatched_report, provider
    )

    assert result.status is ExplanationStatus.FAILED
    assert "submission_id" in (result.error_message or "")
    assert provider.call_count == 0
