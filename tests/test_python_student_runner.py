from pathlib import Path

import pytest

import python_student_runner


def test_python_student_runner_executes_the_requested_script(tmp_path: Path) -> None:
    marker = tmp_path / "result.txt"
    script = tmp_path / "student.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('ok', encoding='utf-8')\n",
        encoding="utf-8",
    )

    assert python_student_runner.main([str(script)]) == 0
    assert marker.read_text(encoding="utf-8") == "ok"


def test_python_student_runner_rejects_invalid_source(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="文件无效"):
        python_student_runner.main([str(tmp_path / "missing.py")])
