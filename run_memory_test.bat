@echo off
REM メモリリーク検証テスト - クイック実行スクリプト
REM
REM 使用方法:
REM   run_memory_test.bat              - 1時間テスト
REM   run_memory_test.bat quick        - 5分クイックテスト
REM   run_memory_test.bat 30           - 30分テスト

echo ========================================
echo KotobaTranscriber メモリリーク検証テスト
echo ========================================
echo.

REM 仮想環境の確認
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: 仮想環境が見つかりません
    echo まず install.bat を実行してください
    pause
    exit /b 1
)

REM 仮想環境をアクティベート
call venv\Scripts\activate.bat

REM 必須ライブラリのチェック
echo 必須ライブラリをチェック中...
python -c "import psutil" 2>nul
if errorlevel 1 (
    echo psutil がインストールされていません
    echo インストールしますか? [Y/N]
    set /p INSTALL_PSUTIL=
    if /i "%INSTALL_PSUTIL%"=="Y" (
        pip install psutil
    ) else (
        echo ERROR: psutil が必要です
        pause
        exit /b 1
    )
)

python -c "import matplotlib" 2>nul
if errorlevel 1 (
    echo matplotlib がインストールされていません（グラフ生成用）
    echo インストールしますか? [Y/N]
    set /p INSTALL_MPL=
    if /i "%INSTALL_MPL%"=="Y" (
        pip install matplotlib
    ) else (
        echo グラフ生成はスキップされます
    )
)

echo.
echo ライブラリチェック完了
echo.

REM テストモードの判定
if "%1"=="quick" (
    echo クイックテストモード（5分）
    python tests\test_memory_leak.py --quick-test
) else if "%1"=="" (
    echo 標準テストモード（1時間）
    echo テストを開始しますか? [Y/N]
    set /p START_TEST=
    if /i "%START_TEST%"=="Y" (
        python tests\test_memory_leak.py
    ) else (
        echo テストをキャンセルしました
        pause
        exit /b 0
    )
) else (
    echo カスタムテストモード（%1 分）
    python tests\test_memory_leak.py --duration %1
)

echo.
echo ========================================
echo テスト完了
echo ========================================
echo.
echo 結果ファイルは logs\memory_test\ に保存されました
echo.
pause
