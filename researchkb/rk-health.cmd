@echo off
setlocal
if "%RESEARCHKB_ROOT%"=="" (
    echo Please set RESEARCHKB_ROOT to your local ResearchKB directory.
    exit /b 2
)
"%RESEARCHKB_ROOT%\.venv\Scripts\python.exe" "%~dp0rk_health.py" %*
