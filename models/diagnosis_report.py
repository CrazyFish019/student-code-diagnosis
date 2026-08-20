"""Aggregate report produced by the rule-based diagnosis engine."""

from __future__ import annotations

from dataclasses import dataclass

from core.exceptions import ModelValidationError
from models.diagnosis import Diagnosis


@dataclass(frozen=True, slots=True)
class DiagnosisReport:
    """A primary diagnosis plus identity and optional secondary evidence.

    ``primary_diagnosis`` is ``None`` when deterministic rules do not provide
    enough evidence. Convenience properties expose the requested flat report
    fields without duplicating validation already owned by ``Diagnosis``.
    """

    submission_id: str
    problem_id: str
    primary_diagnosis: Diagnosis | None
    secondary_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("submission_id", "problem_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ModelValidationError(
                    f"DiagnosisReport.{field_name} must be a non-empty string"
                )
        if self.primary_diagnosis is not None and not isinstance(
            self.primary_diagnosis, Diagnosis
        ):
            raise ModelValidationError(
                "DiagnosisReport.primary_diagnosis must be a Diagnosis or None"
            )
        try:
            secondary_evidence = tuple(self.secondary_evidence)
        except TypeError as exc:
            raise ModelValidationError(
                "DiagnosisReport.secondary_evidence must be iterable"
            ) from exc
        if not all(isinstance(item, str) for item in secondary_evidence):
            raise ModelValidationError(
                "DiagnosisReport.secondary_evidence must contain strings"
            )
        object.__setattr__(self, "secondary_evidence", secondary_evidence)

    @classmethod
    def from_fields(
        cls,
        *,
        submission_id: str,
        problem_id: str,
        category: str,
        summary: str,
        detail: str,
        confidence: float,
        evidence: tuple[str, ...] = (),
        related_lines: tuple[int, ...] = (),
        secondary_evidence: tuple[str, ...] = (),
    ) -> "DiagnosisReport":
        """Create a report while delegating diagnosis validation to Diagnosis."""
        return cls(
            submission_id=submission_id,
            problem_id=problem_id,
            primary_diagnosis=Diagnosis(
                category=category,
                summary=summary,
                detail=detail,
                confidence=confidence,
                related_lines=related_lines,
                evidence=evidence,
            ),
            secondary_evidence=secondary_evidence,
        )

    @property
    def category(self) -> str | None:
        return None if self.primary_diagnosis is None else self.primary_diagnosis.category

    @property
    def summary(self) -> str:
        return "" if self.primary_diagnosis is None else self.primary_diagnosis.summary

    @property
    def detail(self) -> str:
        return "" if self.primary_diagnosis is None else self.primary_diagnosis.detail

    @property
    def confidence(self) -> float:
        return 0.0 if self.primary_diagnosis is None else self.primary_diagnosis.confidence

    @property
    def evidence(self) -> tuple[str, ...]:
        return () if self.primary_diagnosis is None else self.primary_diagnosis.evidence

    @property
    def related_lines(self) -> tuple[int, ...]:
        return () if self.primary_diagnosis is None else self.primary_diagnosis.related_lines
