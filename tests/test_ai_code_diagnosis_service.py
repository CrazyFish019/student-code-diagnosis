import json

import pytest

from models.ai_code_diagnosis import AIConclusion
from models.imported_problem import ImportedProblem, ProblemExample
from services.ai_code_diagnosis_service import (
    AIDiagnosisError,
    diagnose_code,
    test_model_connection as check_model_connection,
)
from services.json_http_client import JsonHttpResponse
from services.settings_service import AppSettings


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request_json(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def problem() -> ImportedProblem:
    return ImportedProblem(
        "https://www.vesibay.cn/problem/AC743",
        "Vesibay",
        "AC743",
        "数组中的行",
        "描述",
        "输入描述",
        "输出描述",
        "提示",
        1000,
        256,
        (ProblemExample("1\n", "2\n"),),
    )


def diagnosis_json(**overrides) -> str:
    payload = {
        "conclusion": "likely_incorrect",
        "summary": "数组行号使用错误",
        "categories": ["array_index_error"],
        "root_cause": "固定访问第0行",
        "evidence": [{"line": 8, "code": "a[0][j]", "explanation": "应使用L"}],
        "sample_analysis": [{"sample_index": 1, "analysis": "可能输出错误"}],
        "suggestions": ["使用a[L][j]"],
        "teacher_feedback": "二维数组基本思路正确。",
        "student_feedback": "检查行下标。",
        "confidence": 0.86,
        "limitations": ["未实际编译运行", "没有隐藏测试数据"],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def completion(content=None, *, finish_reason="stop", status=200):
    return JsonHttpResponse(
        status,
        {
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {"content": content or diagnosis_json()},
                }
            ]
        },
    )


def test_deepseek_non_thinking_request_and_structured_result() -> None:
    transport = FakeTransport(completion())
    source = "int main(){ return 0; }"

    result = diagnose_code(
        problem(),
        source,
        api_key="secret-key",
        settings=AppSettings(),
        transport=transport,
    )

    assert result.conclusion is AIConclusion.LIKELY_INCORRECT
    assert result.confidence == 0.86
    method, url, kwargs = transport.calls[0]
    assert method == "POST"
    assert url == "https://api.deepseek.com/chat/completions"
    assert kwargs["payload"]["thinking"] == {"type": "disabled"}
    assert kwargs["payload"]["temperature"] == 0.2
    assert kwargs["payload"]["response_format"] == {"type": "json_object"}
    prompt = kwargs["payload"]["messages"][1]["content"]
    system_prompt = kwargs["payload"]["messages"][0]["content"]
    assert "数组中的行" in prompt
    assert "输入描述" in prompt
    assert source in prompt
    assert "secret-key" not in prompt
    assert "保留学生源码原有的换行和缩进" in system_prompt
    assert "禁止把多条语句连接成一个长行" in system_prompt


def test_thinking_mode_is_forwarded_for_deepseek() -> None:
    transport = FakeTransport(completion())
    settings = AppSettings(thinking_mode="enabled")

    diagnose_code(problem(), "int main(){}", api_key="key", settings=settings, transport=transport)

    assert transport.calls[0][2]["payload"]["thinking"] == {"type": "enabled"}
    assert "temperature" not in transport.calls[0][2]["payload"]


def test_openai_compatible_request_omits_nonstandard_thinking_field() -> None:
    transport = FakeTransport(completion())
    settings = AppSettings(provider="openai_compatible", base_url="https://example.com/v1", model="custom")

    diagnose_code(problem(), "int main(){}", api_key="key", settings=settings, transport=transport)

    assert "thinking" not in transport.calls[0][2]["payload"]
    assert "temperature" not in transport.calls[0][2]["payload"]


def test_connection_rejects_model_missing_from_account_model_list() -> None:
    transport = FakeTransport(
        JsonHttpResponse(
            200,
            {
                "object": "list",
                "data": [
                    {"id": "kimi-k2.7-code"},
                    {"id": "kimi-k2.6"},
                ],
            },
        )
    )
    settings = AppSettings(
        provider="openai_compatible",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k3",
    )

    with pytest.raises(AIDiagnosisError, match="kimi-k2.7-code"):
        check_model_connection(
            api_key="key", settings=settings, transport=transport
        )


def test_connection_accepts_model_present_in_account_model_list() -> None:
    transport = FakeTransport(
        JsonHttpResponse(
            200,
            {"data": [{"id": "kimi-k2.7-code"}, {"id": "kimi-k2.6"}]},
        )
    )
    settings = AppSettings(
        provider="openai_compatible",
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2.7-code",
    )

    check_model_connection(api_key="key", settings=settings, transport=transport)

    assert transport.calls[0][0] == "GET"
    assert transport.calls[0][1].endswith("/models")


@pytest.mark.parametrize(
    "response,message",
    [
        (completion(status=401), "API Key无效"),
        (completion(status=429), "过于频繁"),
        (completion("not json"), "格式无效"),
        (completion(finish_reason="length"), "被截断"),
        (completion(diagnosis_json(confidence=120)), "confidence"),
    ],
)
def test_model_failures_are_teacher_facing(response, message) -> None:
    with pytest.raises(AIDiagnosisError, match=message):
        diagnose_code(
            problem(),
            "int main(){}",
            api_key="key",
            settings=AppSettings(),
            transport=FakeTransport(response),
        )


def test_empty_source_and_key_are_rejected_before_network() -> None:
    transport = FakeTransport(completion())
    with pytest.raises(AIDiagnosisError, match="粘贴"):
        diagnose_code(problem(), "", api_key="key", settings=AppSettings(), transport=transport)
    with pytest.raises(AIDiagnosisError, match="API Key"):
        diagnose_code(problem(), "int main(){}", api_key="", settings=AppSettings(), transport=transport)
    assert transport.calls == []


def test_common_model_variations_are_normalized_to_strict_model() -> None:
    variant = json.dumps(
        {
            "verdict": "likely_wrong",
            "summary": "存在下标错误",
            "category": "数组越界，逻辑错误",
            "cause": "下标可能超过范围",
            "evidence": [
                {"line": "第 12-13 行", "snippet": "a[i]", "reason": "缺少范围检查"}
            ],
            "sampleAnalysis": ["样例可能得到错误输出"],
            "recommendations": "增加下标范围检查",
            "teacher_explanation": "需要加强边界意识。",
            "student_explanation": "检查数组下标。",
            "confidence": "可信度 82",
            "limitations": [],
            "extra_field": "允许忽略模型意外增加的字段",
        },
        ensure_ascii=False,
    )

    result = diagnose_code(
        problem(),
        "int main(){}",
        api_key="key",
        settings=AppSettings(),
        transport=FakeTransport(completion(variant)),
    )

    assert result.conclusion is AIConclusion.LIKELY_INCORRECT
    assert result.categories == ("array_index_error", "logic_error")
    assert result.evidence[0].line == 12
    assert result.sample_analysis[0].sample_index == 1
    assert result.confidence == 0.82
    assert "未实际编译运行代码" in result.limitations


def test_object_wrapped_text_fields_are_rendered_as_plain_text() -> None:
    variant = diagnosis_json(
        suggestions=[
            {"text": "扩大筛法上界。"},
            {"content": "使用vector保存数组。"},
            {"advice": {"text": "避免无界扫描。"}},
        ],
        teacher_feedback={"text": "主体思路正确，但边界不足。"},
        student_feedback={"content": "请检查上界。"},
        limitations=[{"description": "结论依赖现有测试证据。"}],
    )

    result = diagnose_code(
        problem(),
        "int main(){}",
        api_key="key",
        settings=AppSettings(),
        transport=FakeTransport(completion(variant)),
    )

    assert result.suggestions == (
        "扩大筛法上界。",
        "使用vector保存数组。",
        "避免无界扫描。",
    )
    assert result.teacher_feedback == "主体思路正确，但边界不足。"
    assert result.student_feedback == "请检查上界。"
    assert '{"text"' not in "".join(result.suggestions)


def test_invalid_first_response_is_repaired_once() -> None:
    class RepairTransport:
        def __init__(self):
            self.calls = []

        def request_json(self, method, url, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return completion("{invalid")
            return completion(diagnosis_json())

    transport = RepairTransport()

    result = diagnose_code(
        problem(), "int main(){}", api_key="key", settings=AppSettings(), transport=transport
    )

    assert result.conclusion is AIConclusion.LIKELY_INCORRECT
    assert len(transport.calls) == 2
    assert "上一次JSON未通过本地校验" in transport.calls[1]["payload"]["messages"][-1]["content"]
