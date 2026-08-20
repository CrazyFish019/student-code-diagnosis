"""Orchestrate model requests for structured student-code diagnosis."""

from __future__ import annotations

from typing import Any

from models.ai_code_diagnosis import AICodeDiagnosis
from models.imported_problem import ImportedProblem
from models.vesibay_submission import VesibaySubmissionEvidence
from services.ai_diagnosis_prompt import (
    build_system_prompt as _system_prompt,
    build_user_prompt as _user_prompt,
    has_local_execution as _has_local_execution,
    serialize_oj_evidence as _serialize_oj_evidence,
)
from services.ai_diagnosis_response import (
    ResponseValidationError as _ResponseValidationError,
    normalize_diagnosis_payload as _normalize_diagnosis_payload,
    parse_diagnosis_content as _parse_diagnosis_content,
)
from services.json_http_client import (
    JsonHttpTransport,
    NetworkRequestError,
    UrllibJsonHttpTransport,
)
from services.settings_service import AppSettings


class AIDiagnosisError(RuntimeError):
    """Teacher-facing AI request or response failure."""


def diagnose_code(
    problem: ImportedProblem,
    source_code: str,
    *,
    api_key: str,
    settings: AppSettings,
    oj_evidence: VesibaySubmissionEvidence | None = None,
    selected_case_ids: tuple[str, ...] = (),
    transport: JsonHttpTransport | None = None,
) -> AICodeDiagnosis:
    if not isinstance(problem, ImportedProblem):
        raise TypeError("problem must be an ImportedProblem")
    if not isinstance(source_code, str) or not source_code.strip():
        raise AIDiagnosisError("请粘贴待诊断的C++代码。")
    if len(source_code) > 100_000:
        raise AIDiagnosisError("学生代码过长，请缩短后重试。")
    if not isinstance(api_key, str) or not api_key.strip():
        raise AIDiagnosisError("请填写模型API Key。")
    if oj_evidence is not None:
        if not isinstance(oj_evidence, VesibaySubmissionEvidence):
            raise TypeError("oj_evidence must be a VesibaySubmissionEvidence or None")
        if oj_evidence.problem != problem or oj_evidence.source_code != source_code:
            raise AIDiagnosisError("提交证据与题目或源码不一致。")
        known_case_ids = {case.case_id for case in oj_evidence.cases}
        if any(case_id not in known_case_ids for case_id in selected_case_ids):
            raise AIDiagnosisError("选中的测试点与当前提交不一致。")
    elif selected_case_ids:
        raise AIDiagnosisError("手动粘贴模式不能发送测试点详情。")

    endpoint = f"{settings.base_url.rstrip('/')}/chat/completions"
    request_payload: dict[str, Any] = {
        "model": settings.model,
        "messages": [
            {
                "role": "system",
                "content": _system_prompt(
                    oj_evidence is not None,
                    _has_local_execution(oj_evidence, selected_case_ids),
                ),
            },
            {
                "role": "user",
                "content": _user_prompt(
                    problem,
                    source_code,
                    oj_evidence=oj_evidence,
                    selected_case_ids=selected_case_ids,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
        "max_tokens": settings.max_output_tokens,
    }
    if settings.provider == "deepseek":
        request_payload["thinking"] = {"type": settings.thinking_mode}
        if settings.thinking_mode == "disabled":
            request_payload["temperature"] = 0.2

    active_transport = transport or UrllibJsonHttpTransport()
    first_content = _request_completion(
        active_transport,
        endpoint,
        api_key.strip(),
        request_payload,
        settings.request_timeout_seconds,
    )
    try:
        return _parse_diagnosis_content(
            first_content, has_oj_evidence=oj_evidence is not None
        )
    except _ResponseValidationError as first_error:
        repair_payload = dict(request_payload)
        repair_payload["messages"] = [
            *request_payload["messages"],
            {"role": "assistant", "content": first_content},
            {
                "role": "user",
                "content": (
                    "上一次JSON未通过本地校验："
                    f"{first_error}。请只修正格式和字段类型，重新输出完整JSON对象。"
                ),
            },
        ]
        repaired_content = _request_completion(
            active_transport,
            endpoint,
            api_key.strip(),
            repair_payload,
            settings.request_timeout_seconds,
        )
        try:
            return _parse_diagnosis_content(
                repaired_content, has_oj_evidence=oj_evidence is not None
            )
        except _ResponseValidationError as second_error:
            raise AIDiagnosisError(
                f"模型返回格式无效，自动修复重试仍失败：{second_error}"
            ) from second_error


def test_model_connection(
    *,
    api_key: str,
    settings: AppSettings,
    transport: JsonHttpTransport | None = None,
) -> None:
    if not api_key.strip():
        raise AIDiagnosisError("请填写模型API Key。")
    endpoint = f"{settings.base_url.rstrip('/')}/models"
    try:
        response = (transport or UrllibJsonHttpTransport()).request_json(
            "GET",
            endpoint,
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout_seconds=settings.request_timeout_seconds,
        )
    except NetworkRequestError as exc:
        raise AIDiagnosisError("模型连接失败或超时。") from exc
    _raise_for_status(response.status_code, response.payload)
    available_models = _available_model_ids(response.payload)
    if available_models and settings.model not in available_models:
        visible_models = "、".join(available_models[:12])
        raise AIDiagnosisError(
            f"当前API Key无权使用模型 {settings.model}。"
            f"该账号可用模型：{visible_models}"
        )


def _available_model_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    data = payload.get("data")
    if not isinstance(data, list):
        return ()
    result: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            result.append(model_id.strip())
    return tuple(dict.fromkeys(result))


def _raise_for_status(status_code: int, payload: dict[str, Any]) -> None:
    if 200 <= status_code < 300:
        return
    if status_code == 401:
        raise AIDiagnosisError("API Key无效。")
    if status_code in {402, 403}:
        raise AIDiagnosisError("模型账户余额不足或无权访问该模型。")
    if status_code == 429:
        raise AIDiagnosisError(
            "模型请求过于频繁，服务已限制请求频率；"
            "本次不会自动重试，请等待一段时间后再试。"
        )
    message = payload.get("error")
    if isinstance(message, dict):
        message = message.get("message")
    raise AIDiagnosisError(
        str(message)
        if isinstance(message, str) and message.strip()
        else "模型服务暂时不可用。"
    )


def _request_completion(
    transport: JsonHttpTransport,
    endpoint: str,
    api_key: str,
    request_payload: dict[str, Any],
    timeout_seconds: int,
) -> str:
    try:
        response = transport.request_json(
            "POST",
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            payload=request_payload,
            timeout_seconds=timeout_seconds,
        )
    except NetworkRequestError as exc:
        raise AIDiagnosisError(
            "模型请求失败或超时，本次不会自动重试。"
            "较慢模型建议把请求超时设置为300秒或更高。"
        ) from exc
    _raise_for_status(response.status_code, response.payload)
    try:
        choice = response.payload["choices"][0]
        if choice.get("finish_reason") == "length":
            raise AIDiagnosisError("模型返回内容被截断，请增大最大输出长度。")
        content = choice["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise TypeError
    except AIDiagnosisError:
        raise
    except (KeyError, IndexError, TypeError) as exc:
        raise AIDiagnosisError("模型返回格式无效。") from exc
    return content
