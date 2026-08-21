from pathlib import Path

import launcher
from core.version import UPDATE_REPOSITORY, __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_source_launcher_are_ready() -> None:
    assert __version__ == "1.1.0"
    assert UPDATE_REPOSITORY == "CrazyFish019/student-code-diagnosis"
    assert launcher.application_script() == PROJECT_ROOT / "app.py"
    port = launcher.available_port(18451, 18460)
    assert 18451 <= port <= 18460


def test_packaging_files_do_not_include_runtime_secrets() -> None:
    assert (PROJECT_ROOT / "packaging" / "student_code_diagnosis.spec").is_file()
    installer = (
        PROJECT_ROOT / "packaging" / "student_code_diagnosis.iss"
    ).read_text(encoding="utf-8")
    assert "AppVersion={#MyAppVersion}" in installer
    assert "{localappdata}\\Programs\\StudentCodeDiagnosis" in installer
    assert not (PROJECT_ROOT / "config" / "secrets.json").exists()
    assert not (PROJECT_ROOT / "data" / "diagnosis.db").exists()
    spec = (PROJECT_ROOT / "packaging" / "student_code_diagnosis.spec").read_text(
        encoding="utf-8"
    )
    assert 'name="StudentCodeDiagnosisPythonRunner"' in spec
    assert "runner_executable" in spec
    build_script = (PROJECT_ROOT / "scripts" / "build_windows.ps1").read_text(
        encoding="utf-8"
    )
    assert "StudentCodeDiagnosis-Setup-$version.exe" in build_script
    assert 'Filter "*.exe"' not in build_script


def test_launcher_supports_headless_release_smoke_test(monkeypatch) -> None:
    monkeypatch.setenv("STUDENT_CODE_DIAGNOSIS_NO_BROWSER", "1")
    assert launcher.os.environ["STUDENT_CODE_DIAGNOSIS_NO_BROWSER"] == "1"
    source = (PROJECT_ROOT / "launcher.py").read_text(encoding="utf-8")
    assert '"--global.developmentMode=false"' in source
    assert "pystray.Icon" in source
    assert 'pystray.MenuItem("退出程序"' in source


def test_source_worker_command_starts_the_launcher_in_worker_mode() -> None:
    command = launcher.worker_command(18501)

    assert command[0] == launcher.sys.executable
    assert command[-2:] == ["--streamlit-worker", "18501"]
