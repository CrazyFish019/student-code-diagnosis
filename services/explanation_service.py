"""Interface boundary for a future teaching-explanation implementation."""

from models.ai_explanation import AIExplanation
from models.diagnosis_report import DiagnosisReport


def generate_explanation_placeholder(
    diagnosis_report: DiagnosisReport,
) -> AIExplanation | None:
    """Accept a rule diagnosis and intentionally produce no explanation yet.

    The explicit DiagnosisReport input prevents a future explanation provider
    from bypassing the deterministic diagnosis layer.
    """
    if not isinstance(diagnosis_report, DiagnosisReport):
        raise TypeError("diagnosis_report must be a DiagnosisReport")
    return None
