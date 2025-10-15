@echo off
echo ========================================
echo KotobaTranscriber Installation Script (CPU)
echo ========================================
echo.
echo This script is for PCs without GPU
echo.

echo [1/5] Checking Python version...
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.8 or later from https://www.python.org/
    pause
    exit /b 1
)
echo.

echo [2/5] Upgrading pip...
python -m pip install --upgrade pip
echo.

echo [3/5] Installing PyQt5 and basic packages...
python -m pip install PyQt5 requests
echo.

echo [4/5] Installing AI/ML packages (CPU version)...
echo Installing transformers, torch, torchaudio (CPU version)...
python -m pip install transformers torch torchaudio
echo.

echo [5/5] Installing audio processing packages...
python -m pip install librosa soundfile scikit-learn numpy pandas
echo.

echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo Optional features:
echo   python -m pip install speechbrain
echo.
echo ========================================
echo To start the application:
echo   Run start.bat
echo ========================================
echo.
pause
