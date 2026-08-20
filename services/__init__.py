"""Framework-independent application services."""

from .ai_explanation_service import generate_explanation
from .ai_provider import AIProvider, MockAIProvider
from .compiler import compile_cpp
from .diagnosis_engine import diagnose_submission
from .explanation_service import generate_explanation_placeholder
from .judge_engine import judge_submission
from .history_service import HistoryService, HistoryServiceError
from .report_export import (
    ExportPermissionError,
    ReportExportError,
    export_class_report,
    export_student_feedback,
)
from .result_query import ResultSort, query_results
from .settings_service import AppSettings, SettingsService
from .problem_importer import ProblemImportError, import_public_problem
from .ai_code_diagnosis_service import (
    AIDiagnosisError,
    diagnose_code,
    test_model_connection,
)
from .output_compare import compare_output
from .process_runner import run_process
from .selected_case_runner import SelectedCaseExecutionError, run_selected_testcases
from .teacher_workflow import TeacherWorkflowError, analyze_class

__all__ = [
    "AIProvider",
    "MockAIProvider",
    "compare_output",
    "compile_cpp",
    "diagnose_submission",
    "generate_explanation_placeholder",
    "generate_explanation",
    "judge_submission",
    "HistoryService",
    "HistoryServiceError",
    "AppSettings",
    "SettingsService",
    "ResultSort",
    "query_results",
    "ReportExportError",
    "ExportPermissionError",
    "export_class_report",
    "export_student_feedback",
    "ProblemImportError",
    "import_public_problem",
    "AIDiagnosisError",
    "diagnose_code",
    "test_model_connection",
    "run_process",
    "SelectedCaseExecutionError",
    "run_selected_testcases",
    "TeacherWorkflowError",
    "analyze_class",
]
