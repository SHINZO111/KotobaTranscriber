@echo off
chcp 65001 >nul
echo ============================================
echo KotobaTranscriber - Setup & Test
echo ============================================

cd /d "F:\KotobaTranscriber"

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
echo This may take a while...
pip install -q -r requirements.txt

REM Run tests
echo.
echo Running tests...
python -m pytest tests\ -v --tb=short

echo.
echo ============================================
echo Setup complete!
echo To run the application:
echo   start.bat
echo ============================================
pause
