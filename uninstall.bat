@echo off
REM KotobaTranscriber Uninstaller v2.1
REM Windows用アンインストーラー

echo ========================================
echo KotobaTranscriber アンインストーラー
echo ========================================
echo.

echo このスクリプトは以下を削除します:
echo   - 仮想環境 (venv)
echo   - デスクトップショートカット
echo   - スタートメニュー登録
echo   - 一時ファイル/ログファイル
echo.
echo 注意: ユーザーデータ (app_settings.json, custom_vocabulary.json) は保持されます
echo.

choice /C YN /M "アンインストールを続行しますか？(Y/N)"
if errorlevel 2 (
    echo アンインストールをキャンセルしました
    pause
    exit /b 0
)

echo.
echo [1/5] 実行中のアプリケーションを停止中...
taskkill /IM python.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
echo.

echo [2/5] 仮想環境を削除中...
if exist venv (
    rmdir /s /q venv
    echo 仮想環境を削除しました
) else (
    echo 仮想環境が見つかりません
)
echo.

echo [3/5] 一時ファイルを削除中...
del /q *.log >nul 2>&1
if exist logs (
    del /q logs\*.log >nul 2>&1
)
if exist __pycache__ (
    rmdir /s /q __pycache__
)
if exist src\__pycache__ (
    rmdir /s /q src\__pycache__
)
echo 一時ファイルを削除しました
echo.

echo [4/5] デスクトップショートカットを削除中...
if exist "%USERPROFILE%\Desktop\KotobaTranscriber.lnk" (
    del "%USERPROFILE%\Desktop\KotobaTranscriber.lnk"
    echo デスクトップショートカットを削除しました
) else (
    echo デスクトップショートカットが見つかりません
)
echo.

echo [5/5] スタートメニュー登録を削除中...
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\KotobaTranscriber" (
    rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\KotobaTranscriber"
    echo スタートメニュー登録を削除しました
) else (
    echo スタートメニュー登録が見つかりません
)
echo.

echo ========================================
echo アンインストールが完了しました
echo ========================================
echo.
echo 保持されたファイル:
echo   - ソースコード (src/)
echo   - 設定ファイル (app_settings.json)
echo   - カスタム語彙 (custom_vocabulary.json)
echo   - ドキュメント (docs/, README.md)
echo.
echo これらのファイルを含むフォルダ全体を削除する場合は、
echo 手動でフォルダを削除してください:
echo   %CD%
echo.
pause
