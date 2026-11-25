@echo off
REM UltraRename build script for Windows (ASCII only to avoid codepage issues)
REM Requires Python 3.11+ installed and in PATH

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python not found in PATH. Install Python 3.11+ first.
    pause
    exit /b 1
)

python --version
if not exist .venv (
    python -m venv .venv
)
.venv\Scripts\python -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
.venv\Scripts\python -m PyInstaller --onefile --windowed --name TRename run.py
echo.
echo Build done: dist\UltraRename.exe
pause
