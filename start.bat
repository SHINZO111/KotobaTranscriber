@echo off
echo ========================================
echo Starting KotobaTranscriber...
echo ========================================
echo.

cd /d "%~dp0"

if not exist "src\main.py" (
    echo ERROR: src\main.py not found
    echo Please run this script from KotobaTranscriber folder
    pause
    exit /b 1
)

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python src\main.py
) else (
    python src\main.py
)

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start application
    echo.
    echo Dependencies may not be installed
    echo Please run install.bat or install-cpu.bat
    echo.
    pause
)
