@echo off
echo ========================================
echo Optional Features Installation
echo ========================================
echo.

echo This script installs additional features:
echo   1. speechbrain - Free speaker diarization
echo   2. resemblyzer - Lightweight speaker diarization
echo.

echo [1/2] Installing speechbrain...
echo (Downloads ~200MB model on first use)
python -m pip install speechbrain
echo.

echo [2/2] Installing resemblyzer... (Optional)
echo Press Ctrl+C to skip
timeout /t 5
python -m pip install resemblyzer
echo.

echo ========================================
echo Optional features installed successfully!
echo ========================================
echo.
echo Speaker diarization is now available
echo Enable it via checkbox after starting the app
echo.
pause
