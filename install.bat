@echo off
REM KotobaTranscriber Installer v2.1
REM Windows用インストーラー

echo ========================================
echo KotobaTranscriber インストーラー v2.1
echo ========================================
echo.

REM Pythonバージョンチェック
echo [1/7] Python環境を確認中...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [エラー] Pythonがインストールされていません
    echo Python 3.8以上をインストールしてから再実行してください
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

python --version
echo Python が見つかりました
echo.

REM 仮想環境の作成
echo [2/7] 仮想環境を作成中...
if exist venv (
    echo 既存の仮想環境が見つかりました
    choice /C YN /M "削除して再作成しますか？(Y/N)" /T 10 /D N
    if errorlevel 2 goto skip_venv
    if errorlevel 1 (
        echo 仮想環境を削除中...
        rmdir /s /q venv
    )
)

python -m venv venv
if %errorLevel% neq 0 (
    echo [エラー] 仮想環境の作成に失敗しました
    pause
    exit /b 1
)
echo 仮想環境を作成しました
:skip_venv
echo.

REM 仮想環境の有効化
echo [3/7] 仮想環境を有効化中...
call venv\Scripts\activate.bat
echo.

REM pipのアップグレード
echo [4/7] pipをアップグレード中...
python -m pip install --upgrade pip --quiet
echo.

REM 依存パッケージのインストール
echo [5/7] 依存パッケージをインストール中...
echo これには数分かかる場合があります...
python -m pip install -r requirements.txt --quiet

if %errorLevel% neq 0 (
    echo [エラー] パッケージのインストールに失敗しました
    pause
    exit /b 1
)
echo 依存パッケージをインストールしました
echo.

REM pywin32のインストール
echo [6/7] Windows拡張機能をインストール中...
python -m pip install pywin32 --quiet
echo.

REM GPU対応の確認
echo [7/7] GPU対応を確認中...
python -c "import torch; print('CUDA利用可能:', torch.cuda.is_available())" 2>nul
echo.

echo ========================================
echo インストールが完了しました！
echo ========================================
echo.
echo GPU（CUDA）を使用する場合は、以下を実行してください：
echo   python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
echo.
echo アプリケーションを起動するには：
echo   1. start.bat をダブルクリック
echo   2. または python src\main.py を実行
echo.
echo 詳細な使い方は README.md を参照してください
echo.
pause
