import os
from pathlib import Path
import shutil

import pytest

from models import CompileStatus, ExecutionResult, ExecutionStatus
from services.compiler import compile_cpp
from services.process_runner import run_process


GPP = shutil.which("g++")


def fake_execution(
    status: ExecutionStatus,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        execution_time_ms=5,
    )


def test_compiler_not_found_is_distinct_system_result(tmp_path: Path) -> None:
    result = compile_cpp(
        "int main() { return 0; }\n",
        output_dir=tmp_path,
        compiler="definitely-missing-g++-for-student-code-diagnosis",
    )

    assert result.status is CompileStatus.COMPILER_NOT_FOUND
    assert not result.success
    assert result.executable_path is None
    assert result.exit_code is None
    assert result.error_message


def test_compile_error_keeps_stderr_and_cleans_all_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_source: list[str] = []

    def fake_run(command: list[object], **_: object) -> ExecutionResult:
        source_path = Path(command[1])
        executable_path = Path(command[-1])
        captured_source.append(source_path.read_text(encoding="utf-8"))
        executable_path.write_bytes(b"partial compiler output")
        return fake_execution(
            ExecutionStatus.RUNTIME_ERROR,
            stderr="source.cpp:1: error: expected ';'\n",
            exit_code=1,
        )

    monkeypatch.setattr("services.compiler.run_process", fake_run)
    source = "int main() {\n    broken syntax\n}\n"

    result = compile_cpp(
        source,
        output_dir=tmp_path,
        compiler=Path(os.sys.executable),
        output_name="broken-program",
    )

    assert result.status is CompileStatus.COMPILE_ERROR
    assert "error:" in result.stderr
    assert result.exit_code == 1
    assert captured_source == [source]
    assert not list(tmp_path.glob("*.cpp"))
    assert not [path for path in tmp_path.iterdir() if path.is_file()]


def test_success_output_path_and_caller_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(command: list[object], **_: object) -> ExecutionResult:
        Path(command[-1]).write_bytes(b"executable")
        return fake_execution(ExecutionStatus.SUCCESS, exit_code=0)

    monkeypatch.setattr("services.compiler.run_process", fake_run)

    result = compile_cpp(
        "int main() { return 0; }\n",
        output_dir=tmp_path / "output path with spaces",
        compiler=Path(os.sys.executable),
        output_name="student answer",
    )

    expected_suffix = ".exe" if os.name == "nt" else ""
    assert result.status is CompileStatus.SUCCESS
    assert result.success
    assert result.executable_path == (
        tmp_path / "output path with spaces" / f"student answer{expected_suffix}"
    ).resolve()
    assert result.executable_path.is_file()
    assert not list(result.executable_path.parent.glob("*.cpp"))

    # The caller owns and explicitly removes a successful executable.
    result.executable_path.unlink()


def test_extra_compiler_arguments_are_passed_before_output(monkeypatch, tmp_path) -> None:
    captured_command = []

    def fake_run(command: list[object], **_: object) -> ExecutionResult:
        captured_command.extend(command)
        Path(command[-1]).write_bytes(b"executable")
        return fake_execution(ExecutionStatus.SUCCESS, exit_code=0)

    monkeypatch.setattr("services.compiler.run_process", fake_run)

    result = compile_cpp(
        "int main(){}",
        output_dir=tmp_path,
        compiler=Path(os.sys.executable),
        extra_args=("-Wl,--stack,134217728",),
    )

    assert result.success
    assert "-Wl,--stack,134217728" in captured_command
    assert captured_command.index("-Wl,--stack,134217728") < captured_command.index("-o")
    assert result.executable_path is not None
    result.executable_path.unlink()


def test_compile_timeout_is_not_compile_error_and_cleans_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(command: list[object], **_: object) -> ExecutionResult:
        Path(command[-1]).write_bytes(b"partial")
        return fake_execution(ExecutionStatus.TIMED_OUT, exit_code=-1)

    monkeypatch.setattr("services.compiler.run_process", fake_run)

    result = compile_cpp(
        "int main() {}\n",
        output_dir=tmp_path,
        compiler=Path(os.sys.executable),
    )

    assert result.status is CompileStatus.TIMED_OUT
    assert result.timed_out
    assert result.executable_path is None
    assert not [path for path in tmp_path.iterdir() if path.is_file()]


@pytest.mark.skipif(GPP is None, reason="g++ is not installed or not on PATH")
def test_real_cpp_program_compiles_and_runs_with_stdin(tmp_path: Path) -> None:
    source = (
        "#include <iostream>\n"
        "#include <string>\n"
        "int main() {\n"
        "    std::string line;\n"
        "    while (std::getline(std::cin, line)) std::cout << line << '\\n';\n"
        "    std::cerr << \"compiled stderr\\n\";\n"
        "    return 0;\n"
        "}\n"
    )
    result = compile_cpp(
        source,
        output_dir=tmp_path / "compiled programs with spaces",
        compiler=GPP or "g++",
        output_name="echo program",
        # Hosted Windows runners occasionally need more than the service default
        # while warming the compiler cache. Keep this integration test tolerant.
        timeout_ms=30_000,
    )

    assert result.status is CompileStatus.SUCCESS
    assert result.executable_path is not None
    execution = run_process(
        [result.executable_path],
        stdin_data="line one\nline two\n",
        time_limit_ms=2_000,
    )
    assert execution.status is ExecutionStatus.SUCCESS
    assert execution.stdout == f"line one{os.linesep}line two{os.linesep}"
    assert execution.stderr == f"compiled stderr{os.linesep}"
    result.executable_path.unlink()


@pytest.mark.skipif(GPP is None, reason="g++ is not installed or not on PATH")
def test_real_cpp_syntax_error_returns_compile_error(tmp_path: Path) -> None:
    result = compile_cpp(
        "int main( { this is not valid C++ }\n",
        output_dir=tmp_path,
        compiler=GPP or "g++",
    )

    assert result.status is CompileStatus.COMPILE_ERROR
    assert result.executable_path is None
    assert result.exit_code not in (None, 0)
    assert result.stderr
    assert not list(tmp_path.glob("*.cpp"))
