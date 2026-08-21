from pathlib import Path
import os
import shutil
import time

import services.selected_case_runner as selected_runner
from models.compile_result import CompileResult, CompileStatus
from models.code_language import CodeLanguage
from models.execution_result import ExecutionResult, ExecutionStatus
from models.imported_problem import ImportedProblem
from models.vesibay_submission import OJCaseEvidence, VesibaySubmissionEvidence
from services.selected_case_runner import (
    SelectedCaseExecutionError,
    run_selected_testcases,
)


def _evidence(
    language: CodeLanguage = CodeLanguage.CPP,
    source_code: str = "int main(){}",
) -> VesibaySubmissionEvidence:
    problem = ImportedProblem(
        "https://www.vesibay.cn/problem/P1000",
        "OJ",
        "P1000",
        "A+B",
        "求和",
        "输入",
        "输出",
        "",
        1000,
        128,
    )
    return VesibaySubmissionEvidence(
        "42",
        problem,
        source_code,
        "WA",
        50,
        (
            OJCaseEvidence("1", "AC", 1, 10, "1\n", "1\n", ""),
            OJCaseEvidence("2", "WA", 1, 10, "2\n", "3\n", ""),
            OJCaseEvidence("3", "WA", 1, 10, "4\n", "5\n", ""),
        ),
        language,
    )


def test_selected_cases_compile_once_and_run_in_evidence_order(monkeypatch) -> None:
    compile_calls = []
    run_inputs = []

    def fake_compile(source_code, **kwargs):
        compile_calls.append((source_code, kwargs))
        return CompileResult(
            CompileStatus.SUCCESS,
            Path(kwargs["output_dir"]) / "program.exe",
            "",
            "",
            0,
            10,
        )

    def fake_run(command, *, stdin_data, time_limit_ms, temp_root):
        run_inputs.append((stdin_data, time_limit_ms))
        return ExecutionResult(
            ExecutionStatus.SUCCESS,
            f"actual:{stdin_data}",
            "",
            0,
            2,
        )

    monkeypatch.setattr(selected_runner, "compile_cpp", fake_compile)
    monkeypatch.setattr(selected_runner, "run_process", fake_run)

    result = run_selected_testcases(_evidence(), ("3", "2"))

    assert len(compile_calls) == 1
    expected_extra_args = ("-Wl,--stack,134217728",) if os.name == "nt" else ()
    assert compile_calls[0][1]["extra_args"] == expected_extra_args
    assert run_inputs == [("2\n", 2000), ("4\n", 2000)]
    assert result.cases[0].local_execution_status is None
    assert result.cases[1].locally_captured_stdout == "actual:2\n"
    assert result.cases[2].locally_captured_stdout == "actual:4\n"


def test_compile_failure_stops_before_running_cases(monkeypatch) -> None:
    monkeypatch.setattr(
        selected_runner,
        "compile_cpp",
        lambda *args, **kwargs: CompileResult(
            CompileStatus.COMPILER_NOT_FOUND,
            None,
            "",
            "",
            None,
            0,
        ),
    )
    monkeypatch.setattr(
        selected_runner,
        "run_process",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("runner must not be called")
        ),
    )

    try:
        run_selected_testcases(_evidence(), ("2",))
    except SelectedCaseExecutionError as exc:
        assert "g++" in str(exc)
    else:
        raise AssertionError("compiler failure was not reported")


def test_local_timeout_is_preserved_as_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        selected_runner,
        "compile_cpp",
        lambda source_code, **kwargs: CompileResult(
            CompileStatus.SUCCESS,
            Path(kwargs["output_dir"]) / "program.exe",
            "",
            "",
            0,
            1,
        ),
    )
    monkeypatch.setattr(
        selected_runner,
        "run_process",
        lambda *args, **kwargs: ExecutionResult(
            ExecutionStatus.TIMED_OUT,
            "partial",
            "",
            None,
            2001,
            cleanup_error="tree terminated",
        ),
    )

    result = run_selected_testcases(_evidence(), ("2",))

    case = result.cases[1]
    assert case.local_execution_status is ExecutionStatus.TIMED_OUT
    assert case.locally_captured_stdout == "partial"
    assert case.local_error_message == "tree terminated"


def test_previous_local_results_are_cleared_when_selection_changes(monkeypatch) -> None:
    evidence = _evidence()
    previous = evidence.cases[1]
    previous = previous.__class__(
        previous.case_id,
        previous.status,
        previous.execution_time_ms,
        previous.memory_bytes,
        previous.input_data,
        previous.expected_output,
        previous.user_output,
        previous.error_message,
        ExecutionStatus.SUCCESS,
        "old output",
        "",
        0,
        1,
    )
    evidence = evidence.__class__(
        evidence.submission_id,
        evidence.problem,
        evidence.source_code,
        evidence.final_status,
        evidence.score,
        (evidence.cases[0], previous, evidence.cases[2]),
    )
    monkeypatch.setattr(
        selected_runner,
        "compile_cpp",
        lambda source_code, **kwargs: CompileResult(
            CompileStatus.SUCCESS,
            Path(kwargs["output_dir"]) / "program.exe",
            "",
            "",
            0,
            1,
        ),
    )
    monkeypatch.setattr(
        selected_runner,
        "run_process",
        lambda *args, **kwargs: ExecutionResult(
            ExecutionStatus.SUCCESS, "new output", "", 0, 1
        ),
    )

    result = run_selected_testcases(evidence, ("3",))

    assert result.cases[1].local_execution_status is None
    assert result.cases[1].locally_captured_stdout is None
    assert result.cases[2].locally_captured_stdout == "new output"


def test_python_selected_cases_run_without_calling_cpp_compiler(monkeypatch) -> None:
    monkeypatch.setattr(
        selected_runner,
        "compile_cpp",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Python must not call the C++ compiler")
        ),
    )
    evidence = _evidence(
        CodeLanguage.PYTHON,
        "import sys\nfor line in sys.stdin:\n    print(int(line) + 10)\n",
    )

    result = run_selected_testcases(evidence, ("2", "3"))

    assert result.language is CodeLanguage.PYTHON
    assert result.cases[1].locally_captured_stdout.replace("\r\n", "\n") == "12\n"
    assert result.cases[2].locally_captured_stdout.replace("\r\n", "\n") == "14\n"
    assert all(
        case.local_execution_status is ExecutionStatus.SUCCESS
        for case in result.cases[1:]
    )


def test_python_local_run_preserves_utf8_stdin_and_stdout() -> None:
    evidence = _evidence(
        CodeLanguage.PYTHON,
        "value = input()\nprint('收到：' + value)\n",
    )
    cases = (
        OJCaseEvidence("中文", "WA", 1, 10, "老师\n", "", ""),
    )
    evidence = evidence.__class__(
        evidence.submission_id,
        evidence.problem,
        evidence.source_code,
        evidence.final_status,
        evidence.score,
        cases,
        evidence.language,
    )

    result = run_selected_testcases(evidence, ("中文",))

    assert result.cases[0].locally_captured_stdout.replace(
        "\r\n", "\n"
    ) == "收到：老师\n"


def test_cpp_python_cpp_runs_do_not_share_language_state() -> None:
    if shutil.which("g++") is None:
        raise AssertionError("strict mixed-language test requires g++")
    cpp_source = (
        "#include <iostream>\n"
        "int main(){int x; std::cin>>x; std::cout<<x+1<<'\\n';}\n"
    )
    python_source = "value = int(input())\nprint(value + 20)\n"

    first_cpp = run_selected_testcases(
        _evidence(CodeLanguage.CPP, cpp_source), ("2",)
    )
    python = run_selected_testcases(
        _evidence(CodeLanguage.PYTHON, python_source), ("2",)
    )
    second_cpp = run_selected_testcases(
        _evidence(CodeLanguage.CPP, cpp_source), ("3",)
    )

    assert first_cpp.cases[1].locally_captured_stdout.strip() == "3"
    assert python.cases[1].locally_captured_stdout.strip() == "22"
    assert second_cpp.cases[2].locally_captured_stdout.strip() == "5"


def test_python_nonzero_exit_is_preserved_as_runtime_error() -> None:
    evidence = _evidence(
        CodeLanguage.PYTHON,
        "import sys\nprint('before error')\nsys.exit(7)\n",
    )

    result = run_selected_testcases(evidence, ("2",))

    case = result.cases[1]
    assert case.local_execution_status is ExecutionStatus.RUNTIME_ERROR
    assert case.local_exit_code == 7
    assert case.locally_captured_stdout.strip() == "before error"


def test_python_infinite_loop_times_out_and_is_cleaned_up() -> None:
    evidence = _evidence(CodeLanguage.PYTHON, "while True:\n    pass\n")
    started = time.monotonic()

    result = run_selected_testcases(evidence, ("2",))

    elapsed = time.monotonic() - started
    case = result.cases[1]
    assert case.local_execution_status is ExecutionStatus.TIMED_OUT
    assert elapsed < 8
