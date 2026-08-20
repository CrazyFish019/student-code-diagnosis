"""Explicit success and failure states for explanation generation."""

from dataclasses import dataclass
from enum import Enum

from core.exceptions import ModelValidationError
from models.ai_explanation import AIExplanation


class ExplanationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    """Outcome that keeps absence distinct from provider or parsing failure."""

    status: ExplanationStatus
    explanation: AIExplanation | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExplanationStatus):
            raise ModelValidationError(
                "ExplanationResult.status must be an ExplanationStatus"
            )
        if self.explanation is not None and not isinstance(
            self.explanation, AIExplanation
        ):
            raise ModelValidationError(
                "ExplanationResult.explanation must be an AIExplanation or None"
            )
        if self.error_message is not None and (
            not isinstance(self.error_message, str) or not self.error_message.strip()
        ):
            raise ModelValidationError(
                "ExplanationResult.error_message must be a non-empty string or None"
            )

        if self.status is ExplanationStatus.SUCCESS:
            if self.explanation is None or self.error_message is not None:
                raise ModelValidationError(
                    "SUCCESS requires an explanation and no error_message"
                )
        elif self.status is ExplanationStatus.FAILED:
            if self.explanation is not None or self.error_message is None:
                raise ModelValidationError(
                    "FAILED requires error_message and no explanation"
                )
        elif self.explanation is not None or self.error_message is not None:
            raise ModelValidationError(
                "NOT_AVAILABLE cannot contain explanation or error_message"
            )
