import json

from services.ai_provider import MockAIProvider


def test_mock_provider_returns_fixed_json_and_records_prompt() -> None:
    provider = MockAIProvider()

    response = provider.generate("structured prompt")
    payload = json.loads(response)

    assert payload == {
        "teacher_explanation": "测试解释",
        "student_explanation": "测试反馈",
        "confidence_note": "测试说明",
    }
    assert provider.prompts == ["structured prompt"]
    assert provider.call_count == 1
