@echo off
echo ========================================
echo KotobaTranscriber Installation Script (GPU)
echo ========================================
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
echo This may take several minutes...
python -m pip install PyQt5 requests
echo.

echo [4/5] Installing AI/ML packages with CUDA support...
echo Installing transformers, torch, torchaudio (this will take time)...
python -m pip install transformers torch torchaudio --index-url https://download.pytorch.org/whl/cu118
echo.

echo [5/5] Installing audio processing packages...
python -m pip install librosa soundfile scikit-learn numpy pandas
echo.

echo ========================================
echo Installation completed successfully!
echo ========================================
echo.
echo Optional features:
echo.
echo For speaker diarization (free, no token required):
echo   python -m pip install speechbrain
echo.
echo For advanced AI correction (already installed):
echo   transformers and torch are installed
echo.
echo ========================================
echo To start the application:
echo   Run start.bat
echo   or
echo   python src\main.py
echo ========================================
echo.
pause
