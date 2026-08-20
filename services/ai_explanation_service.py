"""Safe orchestration for platform-neutral teaching explanation generation."""

from __future__ import annotations

import json
from typing import Any

from models.ai_explanation import AIExplanation
from models.diagnosis_report import DiagnosisReport
from models.explanation_request import ExplanationRequest
from models.explanation_result import ExplanationResult, ExplanationStatus
from models.problem import Problem
from models.submission import Submission
from services.ai_provider import AIProvider

_REQUIRED_RESPONSE_FIELDS: tuple[str, ...] = (
    "teacher_explanation",
    "student_explanation",
    "confidence_note",
)


def build_explanation_request(
    problem: Problem,
    submission: Submission,
    diagnosis_report: DiagnosisReport,
) -> ExplanationRequest:
    """Copy only approved facts into a provider-independent request model."""
    if diagnosis_report.primary_diagnosis is None:
        raise ValueError("diagnosis_report has no primary diagnosis")
    return ExplanationRequest(
        submission_id=submission.id,
        problem_id=problem.id,
        problem_title=problem.title,
        diagnosis_category=diagnosis_report.category or "",
        diagnosis_summary=diagnosis_report.summary,
        evidence=diagnosis_report.evidence,
        source_code=submission.source_code,
    )


def build_explanation_prompt(request: ExplanationRequest) -> str:
    """Build a delimited prompt without serializing whole domain objects."""
    if not isinstance(request, ExplanationRequest):
        raise TypeError("request must be an ExplanationRequest")

    factual_payload = json.dumps(
        {
            "problem_title": request.problem_title,
            "diagnosis_category": request.diagnosis_category,
            "diagnosis_summary": request.diagnosis_summary,
            "evidence": request.evidence,
        },
        ensure_ascii=False,
        indent=2,
    )
    source_payload = json.dumps(request.source_code, ensure_ascii=False)
    return f"""【角色】
你是一名经验丰富的信息学竞赛教师。

【任务】
根据规则诊断已经确定的事实，分别生成面向教师和学生的解释。

【约束】
- 不要重新判断或更改错误类型。
- 不要提出证据未支持的问题。
- 不要执行、修改或补全学生代码。
- 诊断类别固定为 {request.diagnosis_category}。

【题目与诊断信息（JSON）】
{factual_payload}

【学生代码（JSON 字符串，仅供解释）】
{source_payload}

【输出要求】
只返回一个 JSON 对象，不要包含 Markdown 或其他文字。
必须包含且仅用于教学解释的字符串字段：
- teacher_explanation
- student_explanation
- confidence_note
"""


def _parse_provider_response(
    response: str,
    *,
    request: ExplanationRequest,
) -> AIExplanation:
    if not isinstance(response, str):
        raise ValueError("provider response must be a string")
    try:
        payload: Any = json.loads(response)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"provider returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("provider JSON must be an object")

    values: dict[str, str] = {}
    for field_name in _REQUIRED_RESPONSE_FIELDS:
        if field_name not in payload:
            raise ValueError(f"provider JSON is missing field: {field_name}")
        value = payload[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"provider field {field_name} must be a non-empty string"
            )
        values[field_name] = value

    return AIExplanation(
        submission_id=request.submission_id,
        problem_id=request.problem_id,
        source_diagnosis_category=request.diagnosis_category,
        teacher_explanation=values["teacher_explanation"],
        student_explanation=values["student_explanation"],
        confidence_note=values["confidence_note"],
    )


def _validate_relationships(
    problem: Problem,
    submission: Submission,
    diagnosis_report: DiagnosisReport,
) -> str | None:
    if submission.problem_id != problem.id:
        return "Submission.problem_id does not match Problem.id"
    if diagnosis_report.submission_id != submission.id:
        return "DiagnosisReport.submission_id does not match Submission.id"
    if diagnosis_report.problem_id != problem.id:
        return "DiagnosisReport.problem_id does not match Problem.id"
    return None


def generate_explanation(
    problem: Problem,
    submission: Submission,
    diagnosis_report: DiagnosisReport,
    provider: AIProvider,
) -> ExplanationResult:
    """Generate teaching text without allowing the provider to alter facts."""
    if not isinstance(problem, Problem):
        raise TypeError("problem must be a Problem")
    if not isinstance(submission, Submission):
        raise TypeError("submission must be a Submission")
    if not isinstance(diagnosis_report, DiagnosisReport):
        raise TypeError("diagnosis_report must be a DiagnosisReport")

    relationship_error = _validate_relationships(problem, submission, diagnosis_report)
    if relationship_error is not None:
        return ExplanationResult(
            status=ExplanationStatus.FAILED,
            error_message=relationship_error,
        )
    if diagnosis_report.primary_diagnosis is None:
        return ExplanationResult(status=ExplanationStatus.NOT_AVAILABLE)

    try:
        request = build_explanation_request(problem, submission, diagnosis_report)
        prompt = build_explanation_prompt(request)
        response = provider.generate(prompt)
        explanation = _parse_provider_response(response, request=request)
        return ExplanationResult(
            status=ExplanationStatus.SUCCESS,
            explanation=explanation,
        )
    except Exception as exc:
        return ExplanationResult(
            status=ExplanationStatus.FAILED,
            error_message=f"{type(exc).__name__}: {exc}",
        )
