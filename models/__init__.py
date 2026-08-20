"""Strongly typed domain models for Student Code Diagnosis."""

from .ai_explanation import AIExplanation
from .ai_code_diagnosis import (
    AIConclusion,
    AICodeDiagnosis,
    CodeEvidence,
    SampleAnalysis,
)
from .imported_problem import ImportedProblem, ProblemExample
from .compile_result import CompileResult, CompileStatus
from .diagnosis import Diagnosis
from .diagnosis_report import DiagnosisReport
from .execution_result import ExecutionResult, ExecutionStatus
from .explanation_request import ExplanationRequest
from .explanation_result import ExplanationResult, ExplanationStatus
from .judge_result import JudgeResult, JudgeStatus, TestCaseResult
from .history import (
    DiagnosisRecord,
    ExplanationRecord,
    HistoricalStudent,
    HistoricalTask,
    SubmissionRecord,
    TaskRecord,
)
from .problem import Problem
from .submission import Submission
from .testcase import TestCase
from .workbench import ClassAnalysisResult, StudentAnalysis, StudentSource
from .vesibay_submission import OJCaseEvidence, VesibaySubmissionEvidence

__all__ = [
    "AIExplanation",
    "AIConclusion",
    "AICodeDiagnosis",
    "CodeEvidence",
    "SampleAnalysis",
    "ImportedProblem",
    "ProblemExample",
    "CompileResult",
    "CompileStatus",
    "Diagnosis",
    "DiagnosisReport",
    "ExecutionResult",
    "ExecutionStatus",
    "ExplanationRequest",
    "ExplanationResult",
    "ExplanationStatus",
    "JudgeResult",
    "JudgeStatus",
    "Problem",
    "Submission",
    "TestCase",
    "TestCaseResult",
    "ClassAnalysisResult",
    "StudentAnalysis",
    "StudentSource",
    "DiagnosisRecord",
    "ExplanationRecord",
    "HistoricalStudent",
    "HistoricalTask",
    "SubmissionRecord",
    "TaskRecord",
    "OJCaseEvidence",
    "VesibaySubmissionEvidence",
]
