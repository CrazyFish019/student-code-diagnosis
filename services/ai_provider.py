"""Platform-neutral explanation provider contract and deterministic test double."""

from __future__ import annotations

import json
from typing import Protocol


class AIProvider(Protocol):
    """Minimal contract implemented by any future explanation provider."""

    def generate(self, prompt: str) -> str:
        """Return provider text for one structured prompt."""
        ...


_DEFAULT_MOCK_PAYLOAD = {
    "teacher_explanation": "测试解释",
    "student_explanation": "测试反馈",
    "confidence_note": "测试说明",
}


class MockAIProvider:
    """Deterministic provider used only by tests and local integration checks."""

    def __init__(self, response: str | None = None) -> None:
        self._response = (
            json.dumps(_DEFAULT_MOCK_PAYLOAD, ensure_ascii=False)
            if response is None
            else response
        )
        self.prompts: list[str] = []

    @property
    def call_count(self) -> int:
        return len(self.prompts)

    def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")
        self.prompts.append(prompt)
        return self._response
