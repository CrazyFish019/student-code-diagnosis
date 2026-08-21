from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_root = Path(SPEC).resolve().parent.parent
streamlit_data, streamlit_binaries, streamlit_hidden = collect_all("streamlit")

analysis = Analysis(
    [str(project_root / "launcher.py")],
    pathex=[str(project_root)],
    binaries=streamlit_binaries,
    datas=[
        *streamlit_data,
        *copy_metadata("streamlit"),
        *copy_metadata("openpyxl"),
        (str(project_root / "app.py"), "."),
    ],
    hiddenimports=streamlit_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="StudentCodeDiagnosis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

runner_analysis = Analysis(
    [str(project_root / "python_student_runner.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
runner_pyz = PYZ(runner_analysis.pure)
runner_executable = EXE(
    runner_pyz,
    runner_analysis.scripts,
    [],
    exclude_binaries=True,
    name="StudentCodeDiagnosisPythonRunner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
collection = COLLECT(
    executable,
    runner_executable,
    analysis.binaries,
    analysis.datas,
    runner_analysis.binaries,
    runner_analysis.datas,
    strip=False,
    upx=False,
    name="StudentCodeDiagnosis",
)
