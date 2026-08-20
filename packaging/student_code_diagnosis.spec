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
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="StudentCodeDiagnosis",
)
