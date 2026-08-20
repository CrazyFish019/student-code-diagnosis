from dataclasses import FrozenInstanceError

import pytest

from core.exceptions import ModelValidationError
from models import Diagnosis


def make_diagnosis(**overrides: object) -> Diagnosis:
    values: dict[str, object] = {
        "category": "off_by_one",
        "summary": "Loop bound is too large.",
        "detail": "The last iteration accesses beyond the array.",
        "confidence": 0.8,
        "related_lines": [12, 13],
        "evidence": ["Runtime error on the maximum-size case."],
    }
    values.update(overrides)
    return Diagnosis(**values)  # type: ignore[arg-type]


def test_diagnosis_creation_converts_collections_to_tuples() -> None:
    diagnosis = make_diagnosis()

    assert diagnosis.confidence == 0.8
    assert diagnosis.related_lines == (12, 13)
    assert isinstance(diagnosis.evidence, tuple)


@pytest.mark.parametrize("confidence", [-0.01, -1])
def test_diagnosis_rejects_confidence_below_zero(confidence: float) -> None:
    with pytest.raises(ModelValidationError, match="confidence"):
        make_diagnosis(confidence=confidence)


@pytest.mark.parametrize("confidence", [1.01, 2])
def test_diagnosis_rejects_confidence_above_one(confidence: float) -> None:
    with pytest.raises(ModelValidationError, match="confidence"):
        make_diagnosis(confidence=confidence)


@pytest.mark.parametrize("confidence", [0, 1])
def test_diagnosis_accepts_confidence_boundaries(confidence: int) -> None:
    assert make_diagnosis(confidence=confidence).confidence == float(confidence)


def test_diagnosis_is_immutable() -> None:
    diagnosis = make_diagnosis()

    with pytest.raises(FrozenInstanceError):
        diagnosis.confidence = 0.2  # type: ignore[misc]
