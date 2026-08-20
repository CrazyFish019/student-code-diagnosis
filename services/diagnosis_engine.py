"""Rule-based explanation of an existing deterministic JudgeResult."""

from __future__ import annotations

from core.exceptions import ModelValidationError
from models.diagnosis_report import DiagnosisReport
from models.judge_result import JudgeResult
from models.problem import Problem
from models.submission import Submission
from services.diagnosis_rules import DIAGNOSIS_RULES, DiagnosisContext


def diagnose_submission(
    problem: Problem,
    submission: Submission,
    judge_result: JudgeResult,
) -> DiagnosisReport:
    """Return the highest-priority diagnosis supported by deterministic evidence."""
    if not isinstance(problem, Problem):
        raise TypeError("problem must be a Problem")
    if not isinstance(submission, Submission):
        raise TypeError("submission must be a Submission")
    if not isinstance(judge_result, JudgeResult):
        raise TypeError("judge_result must be a JudgeResult")
    if submission.problem_id != problem.id:
        raise ModelValidationError(
            "Submission.problem_id must match the diagnosed Problem.id"
        )
    if judge_result.submission_id != submission.id:
        raise ModelValidationError(
            "JudgeResult.submission_id must match Submission.id"
        )
    if judge_result.problem_id != problem.id:
        raise ModelValidationError("JudgeResult.problem_id must match Problem.id")

    context = DiagnosisContext(problem, submission, judge_result)
    for rule in DIAGNOSIS_RULES:
        outcome = rule(context)
        if outcome is not None:
            return DiagnosisReport(
                submission_id=submission.id,
                problem_id=problem.id,
                primary_diagnosis=outcome.diagnosis,
                secondary_evidence=outcome.secondary_evidence,
            )

    return DiagnosisReport(
        submission_id=submission.id,
        problem_id=problem.id,
        primary_diagnosis=None,
        secondary_evidence=("现有规则没有找到足够可靠的主要诊断证据。",),
    )
