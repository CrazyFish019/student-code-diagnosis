"""Compile once and locally run only teacher-selected OJ testcases."""

from __future__ import annotations

import tempfile
import os
from dataclasses import replace
from pathlib import Path

from core.config import TEMP_DIR
from models.compile_result import CompileStatus
from models.vesibay_submission import VesibaySubmissionEvidence
from services.compiler import compile_cpp
from services.process_runner import run_process


class SelectedCaseExecutionError(RuntimeError):
    """Teacher-facing failure before selected-case evidence can be produced."""


def run_selected_testcases(
    evidence: VesibaySubmissionEvidence,
    selected_case_ids: tuple[str, ...],
    *,
    compiler: str | Path = "g++",
    compile_timeout_ms: int = 20_000,
) -> VesibaySubmissionEvidence:
    """Return a copy enriched with local results for the selected cases only.

    The executable and all source/run directories are owned by this service and
    removed before it returns. This is controlled execution, not an OS sandbox.
    """

    if not isinstance(evidence, VesibaySubmissionEvidence):
        raise TypeError("evidence must be a VesibaySubmissionEvidence")
    selected_ids = tuple(selected_case_ids)
    if not selected_ids:
        raise SelectedCaseExecutionError("请先选择至少一个测试点。")
    if len(set(selected_ids)) != len(selected_ids):
        raise SelectedCaseExecutionError("选中的测试点存在重复项。")
    known_ids = {case.case_id for case in evidence.cases}
    if any(case_id not in known_ids for case_id in selected_ids):
        raise SelectedCaseExecutionError("选中的测试点与当前提交不一致。")

    local_time_limit_ms = max(
        2_000, min(30_000, evidence.problem.time_limit_ms * 2)
    )
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="student-diagnosis-selected-", dir=TEMP_DIR
        ) as root:
            compiled = compile_cpp(
                evidence.source_code,
                output_dir=root,
                timeout_ms=compile_timeout_ms,
                compiler=compiler,
                output_name="selected-case-program",
                extra_args=(
                    ("-Wl,--stack,134217728",) if os.name == "nt" else ()
                ),
            )
            if not compiled.success:
                raise SelectedCaseExecutionError(_compile_failure_message(compiled.status))
            assert compiled.executable_path is not None
            selected_set = set(selected_ids)
            enriched_cases = []
            for case in evidence.cases:
                clean_case = replace(
                    case,
                    local_execution_status=None,
                    locally_captured_stdout=None,
                    locally_captured_stderr=None,
                    local_exit_code=None,
                    local_execution_time_ms=None,
                    local_error_message=None,
                )
                if case.case_id not in selected_set:
                    enriched_cases.append(clean_case)
                    continue
                execution = run_process(
                    [compiled.executable_path],
                    stdin_data=case.input_data,
                    time_limit_ms=local_time_limit_ms,
                    temp_root=root,
                )
                enriched_cases.append(
                    replace(
                        clean_case,
                        local_execution_status=execution.status,
                        locally_captured_stdout=execution.stdout,
                        locally_captured_stderr=execution.stderr,
                        local_exit_code=execution.exit_code,
                        local_execution_time_ms=execution.execution_time_ms,
                        local_error_message=(
                            execution.error_message or execution.cleanup_error
                        ),
                    )
                )
            return replace(evidence, cases=tuple(enriched_cases))
    except SelectedCaseExecutionError:
        raise
    except OSError as exc:
        raise SelectedCaseExecutionError("无法创建或清理本地临时运行目录。") from exc


def _compile_failure_message(status: CompileStatus) -> str:
    if status is CompileStatus.COMPILER_NOT_FOUND:
        return "本地编译器不可用，请检查g++配置。"
    if status is CompileStatus.COMPILE_ERROR:
        return "学生代码无法在本机编译，不能获取实际输出。"
    if status is CompileStatus.TIMED_OUT:
        return "学生代码本地编译超时，不能获取实际输出。"
    return "本地编译基础设施异常，不能获取实际输出。"
