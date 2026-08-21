import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from models import ExecutionStatus
from services.process_runner import decode_captured_output, run_process


def test_windows_runner_configuration_prevents_console_flash() -> None:
    if os.name != "nt":
        return
    source_path = (
        Path(__file__).resolve().parents[1] / "services" / "process_runner.py"
    )
    source = source_path.read_text(encoding="utf-8")
    assert "subprocess.CREATE_NO_WINDOW" in source


def python_command(code: str, *arguments: str | Path) -> list[str | Path]:
    return [Path(sys.executable), "-c", code, *arguments]


def test_process_reads_multiline_stdin_and_captures_stdout() -> None:
    input_data = "first line\n中文内容\nlast line\n"

    result = run_process(
        python_command(
            "import sys; data = sys.stdin.buffer.read(); sys.stdout.buffer.write(data)"
        ),
        stdin_data=input_data,
        time_limit_ms=2_000,
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert result.stdout == input_data
    assert result.stderr == ""
    assert result.exit_code == 0


def test_process_captures_stderr() -> None:
    result = run_process(
        python_command("import sys; sys.stderr.buffer.write(b'diagnostic\\n')"),
        stdin_data="",
        time_limit_ms=2_000,
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert result.stderr == "diagnostic\n"


def test_nonzero_exit_code_is_runtime_error_result() -> None:
    result = run_process(
        python_command("import sys; sys.exit(7)"),
        stdin_data="",
        time_limit_ms=2_000,
    )

    assert result.status is ExecutionStatus.RUNTIME_ERROR
    assert result.exit_code == 7
    assert not result.timed_out


def test_infinite_loop_times_out_in_reasonable_wall_time() -> None:
    started_at = time.perf_counter()
    result = run_process(
        python_command("while True: pass"),
        stdin_data="",
        time_limit_ms=200,
    )
    wall_time = time.perf_counter() - started_at

    assert result.status is ExecutionStatus.TIMED_OUT
    assert result.timed_out
    assert wall_time < 5
    assert result.execution_time_ms >= 100


def test_missing_executable_is_start_failure() -> None:
    missing = Path("definitely-missing-program-for-student-code-diagnosis.exe")

    result = run_process([missing], stdin_data="", time_limit_ms=1_000)

    assert result.status is ExecutionStatus.START_FAILED
    assert result.exit_code is None
    assert result.error_message


def test_empty_input_and_empty_output() -> None:
    result = run_process(
        python_command("import sys; assert sys.stdin.buffer.read() == b''"),
        stdin_data="",
        time_limit_ms=2_000,
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert result.stdout == ""
    assert result.stderr == ""


def test_invalid_output_bytes_never_crash_decoder() -> None:
    result = run_process(
        python_command("import os; os.write(1, bytes([255, 254, 65]))"),
        stdin_data="",
        time_limit_ms=2_000,
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert isinstance(result.stdout, str)
    assert "A" in result.stdout
    assert decode_captured_output(b"valid utf-8: \xe4\xb8\xad\xe6\x96\x87") == "valid utf-8: 中文"


def test_script_path_with_spaces_is_passed_as_one_argument(tmp_path: Path) -> None:
    directory = tmp_path / "directory with spaces"
    directory.mkdir()
    script = directory / "echo input.py"
    script.write_text(
        "import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )

    result = run_process(
        [Path(sys.executable), script],
        stdin_data="space-safe\n",
        time_limit_ms=2_000,
    )

    assert result.status is ExecutionStatus.SUCCESS
    assert result.stdout == "space-safe\n"


def test_temporary_working_directory_is_removed(
    tmp_path: Path,
) -> None:
    recorded_path = tmp_path / "working-directory.txt"
    result = run_process(
        python_command(
            "from pathlib import Path; import os, sys; "
            "Path(sys.argv[1]).write_text(os.getcwd(), encoding='utf-8')",
            recorded_path,
        ),
        stdin_data="",
        time_limit_ms=2_000,
        temp_root=tmp_path,
    )

    working_directory = Path(recorded_path.read_text(encoding="utf-8"))
    assert result.status is ExecutionStatus.SUCCESS
    assert not working_directory.exists()
    assert not list(tmp_path.glob("student-code-run-*"))


def test_timeout_terminates_child_process_tree(tmp_path: Path) -> None:
    spawned_marker = tmp_path / "child-spawned.txt"
    survivor_marker = tmp_path / "child-survived.txt"
    child_code = (
        "import pathlib, sys, time; time.sleep(1.2); "
        "pathlib.Path(sys.argv[1]).write_text('survived', encoding='utf-8')"
    )
    parent_code = (
        "import pathlib, subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[3]]); "
        "pathlib.Path(sys.argv[2]).write_text('spawned', encoding='utf-8'); "
        "time.sleep(30)"
    )

    result = run_process(
        python_command(
            parent_code,
            child_code,
            spawned_marker,
            survivor_marker,
        ),
        stdin_data="",
        time_limit_ms=800,
    )

    assert result.status is ExecutionStatus.TIMED_OUT
    assert spawned_marker.exists(), "the child must exist before cleanup is tested"
    time.sleep(0.8)
    assert not survivor_marker.exists()


@pytest.mark.parametrize("invalid_limit", [0, -1])
def test_invalid_time_limit_is_rejected(invalid_limit: int) -> None:
    with pytest.raises(ValueError, match="time_limit_ms"):
        run_process(
            python_command("pass"),
            stdin_data="",
            time_limit_ms=invalid_limit,
        )
