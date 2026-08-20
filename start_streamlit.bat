@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_COMMAND=py"
    goto start_app
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_COMMAND=python"
    goto start_app
)

echo [Error] Python was not found. Please install Python 3.11 or newer.
pause
exit /b 1

:start_app
echo Starting Student Code Diagnosis...
%PYTHON_COMMAND% -m streamlit run app.py --server.headless false

if %errorlevel% neq 0 (
    echo.
    echo [Error] Streamlit failed to start.
    echo Run: %PYTHON_COMMAND% -m pip install -r requirements.txt
    pause
    exit /b 1
)

endlocal
