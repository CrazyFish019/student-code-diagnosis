"""Normalize OpenAI-compatible responses into strict diagnosis models."""

from __future__ import annotations

import json
import re
from typing import Any

from models.ai_code_diagnosis import (
    AIConclusion,
    AICodeDiagnosis,
    CodeEvidence,
    SampleAnalysis,
)


_CATEGORY_ALIASES = {
    "syntax_error": "syntax_error",
    "语法错误": "syntax_error",
    "compile_error": "compile_risk",
    "compile_risk": "compile_risk",
    "编译错误": "compile_risk",
    "编译风险": "compile_risk",
    "logic_error": "logic_error",
    "runtime_error": "logic_error",
    "逻辑错误": "logic_error",
    "boundary_error": "boundary_error",
    "边界错误": "boundary_error",
    "input_error": "input_error",
    "输入错误": "input_error",
    "output_format_error": "output_format_error",
    "输出格式错误": "output_format_error",
    "complexity_risk": "complexity_risk",
    "performance_issue": "complexity_risk",
    "复杂度问题": "complexity_risk",
    "data_type_error": "data_type_error",
    "数据类型错误": "data_type_error",
    "array_index_error": "array_index_error",
    "数组越界": "array_index_error",
    "uncertain": "uncertain",
    "不确定": "uncertain",
}


class ResponseValidationError(ValueError):
    pass


def parse_diagnosis_content(
    content: str, *, has_oj_evidence: bool = False
) -> AICodeDiagnosis:
    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE
            )
        raw = json.loads(cleaned)
        if isinstance(raw, dict) and isinstance(raw.get("diagnosis"), dict):
            raw = raw["diagnosis"]
        if not isinstance(raw, dict):
            raise ResponseValidationError("JSON顶层不是对象")
        normalized = normalize_diagnosis_payload(
            raw, has_oj_evidence=has_oj_evidence
        )
        return AICodeDiagnosis(
            conclusion=AIConclusion(normalized["conclusion"]),
            summary=normalized["summary"],
            categories=normalized["categories"],
            root_cause=normalized["root_cause"],
            evidence=normalized["evidence"],
            sample_analysis=normalized["sample_analysis"],
            suggestions=normalized["suggestions"],
            teacher_feedback=normalized["teacher_feedback"],
            student_feedback=normalized["student_feedback"],
            confidence=normalized["confidence"],
            limitations=normalized["limitations"],
        )
    except ResponseValidationError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ResponseValidationError(f"字段类型或取值无效：{exc}") from exc


def normalize_diagnosis_payload(
    payload: dict[str, Any], *, has_oj_evidence: bool = False
) -> dict[str, Any]:
    summary = _first_text(payload, "summary", "diagnosis_summary", "概述")
    root_cause = _first_text(
        payload, "root_cause", "rootCause", "cause", default=summary
    )
    conclusion = _normalize_conclusion(payload.get("conclusion", payload.get("verdict")))
    categories = _normalize_categories(payload.get("categories", payload.get("category")))
    evidence = _normalize_evidence(payload.get("evidence", []))
    sample_analysis = _normalize_sample_analysis(
        payload.get("sample_analysis", payload.get("sampleAnalysis", []))
    )
    suggestions = _normalize_text_list(
        payload.get("suggestions", payload.get("recommendations")),
        fallback=(root_cause,),
    )
    teacher_feedback = _first_text(
        payload, "teacher_feedback", "teacher_explanation", default=summary
    )
    student_feedback = _first_text(
        payload, "student_feedback", "student_explanation", default=suggestions[0]
    )
    confidence = _normalize_confidence(payload.get("confidence", 0.5))
    limitations = list(_normalize_text_list(payload.get("limitations"), fallback=()))
    if has_oj_evidence:
        limitations = [
            item for item in limitations if "没有使用隐藏测试数据" not in item
        ]
        required_limitations = ("本工具没有重新运行代码，结论基于OJ已有判题记录",)
    else:
        required_limitations = ("未实际编译运行代码", "没有使用隐藏测试数据")
    for required in required_limitations:
        if not any(required in item for item in limitations):
            limitations.append(required)
    return {
        "conclusion": conclusion,
        "summary": summary,
        "categories": categories,
        "root_cause": root_cause,
        "evidence": evidence,
        "sample_analysis": sample_analysis,
        "suggestions": suggestions,
        "teacher_feedback": teacher_feedback,
        "student_feedback": student_feedback,
        "confidence": confidence,
        "limitations": tuple(limitations),
    }


def _normalize_conclusion(value: Any) -> str:
    aliases = {
        "likely_correct": "likely_correct",
        "correct": "likely_correct",
        "可能正确": "likely_correct",
        "likely_incorrect": "likely_incorrect",
        "likely_wrong": "likely_incorrect",
        "incorrect": "likely_incorrect",
        "可能错误": "likely_incorrect",
        "可能存在错误": "likely_incorrect",
        "uncertain": "uncertain",
        "unknown": "uncertain",
        "不确定": "uncertain",
    }
    key = str(value).strip().lower()
    if key not in aliases:
        raise ResponseValidationError(f"未知结论：{value}")
    return aliases[key]


def _normalize_categories(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = [item.strip() for item in re.split(r"[,，、;；]", value)]
    elif isinstance(value, list):
        candidates = [
            str(
                item.get(
                    "category",
                    item.get("name", item.get("type", item.get("text", item.get("value", "")))),
                )
            ).strip()
            if isinstance(item, dict)
            else str(item).strip()
            for item in value
        ]
    else:
        candidates = []
    normalized = tuple(
        dict.fromkeys(
            _CATEGORY_ALIASES[item.lower()]
            for item in candidates
            if item and item.lower() in _CATEGORY_ALIASES
        )
    )
    return normalized or ("uncertain",)


def _normalize_evidence(value: Any) -> tuple[CodeEvidence, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return ()
    result: list[CodeEvidence] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(CodeEvidence(None, "", item))
        elif isinstance(item, dict):
            explanation = _first_text(
                item, "explanation", "reason", "description", default=""
            )
            code = item.get("code", item.get("snippet", ""))
            if not isinstance(code, str):
                code = str(code)
            if explanation:
                result.append(
                    CodeEvidence(_normalize_line(item.get("line")), code, explanation)
                )
    return tuple(result)


def _normalize_sample_analysis(value: Any) -> tuple[SampleAnalysis, ...]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return ()
    result: list[SampleAnalysis] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, str) and item.strip():
            result.append(SampleAnalysis(index, item))
        elif isinstance(item, dict):
            analysis = _first_text(item, "analysis", "explanation", "result", default="")
            sample_index = _normalize_line(
                item.get("sample_index", item.get("index"))
            ) or index
            if analysis:
                result.append(SampleAnalysis(sample_index, analysis))
    return tuple(result)


def _normalize_line(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    match = re.search(r"\d+", str(value))
    if match:
        number = int(match.group())
        return number if number > 0 else None
    return None


def _normalize_confidence(value: Any) -> float:
    if isinstance(value, bool):
        raise ResponseValidationError("confidence不是数字")
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            value = float(text[:-1]) / 100
        else:
            match = re.search(r"-?\d+(?:\.\d+)?", text)
            if match is None:
                raise ResponseValidationError("confidence不是数字")
            value = float(match.group())
    result = float(value)
    if 1 < result <= 100:
        result /= 100
    if not 0 <= result <= 1:
        raise ResponseValidationError("confidence超出0到1")
    return result


def _normalize_text_list(value: Any, *, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, list):
        values = tuple(value)
    elif isinstance(value, dict):
        if any(
            key in value
            for key in ("text", "content", "suggestion", "advice", "description")
        ):
            values = (value,)
        else:
            values = tuple(value.values())
    else:
        values = ()
    cleaned = tuple(text for item in values if (text := _coerce_text(item)))
    return cleaned or fallback


def _first_text(
    payload: dict[str, Any], *keys: str, default: str | None = None
) -> str:
    for key in keys:
        value = _coerce_text(payload.get(key))
        if value:
            return value
    if default is not None:
        return default
    raise ResponseValidationError(f"缺少非空字段：{keys[0]}")


def _coerce_text(value: Any) -> str:
    """Extract display text from common OpenAI-compatible JSON shapes."""

    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in (
            "text",
            "content",
            "suggestion",
            "advice",
            "description",
            "explanation",
            "message",
            "value",
        ):
            if key in value:
                text = _coerce_text(value[key])
                if text:
                    return text
        if len(value) == 1:
            return _coerce_text(next(iter(value.values())))
    return ""
