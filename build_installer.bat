@echo off
REM KotobaTranscriber Installer Builder
REM このスクリプトはPyInstallerとNSISを使用して配布用インストーラーを作成します
REM 事前に以下をインストール: PyInstaller, NSIS

echo ========================================
echo KotobaTranscriber Installer Builder v2.1
echo ========================================
echo.

REM 前提条件チェック
echo [1/5] 前提条件をチェック中...

REM PyInstallerのインストール確認
pyinstaller --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [エラー] PyInstallerがインストールされていません
    echo 以下を実行してインストール: pip install pyinstaller
    pause
    exit /b 1
)
echo PyInstaller: OK

REM NSISのインストール確認
where makensis >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] NSISがインストールされていません
    echo 以下からダウンロードしてインストール: https://nsis.sourceforge.io
    echo NSISをインストール後、PATHに追加してください
    pause
    exit /b 1
)
echo NSIS: OK
echo.

REM dist ディレクトリのクリア
echo [2/5] 前回のビルドをクリア中...
if exist dist (
    rmdir /s /q dist
)
if exist build (
    rmdir /s /q build
)
if exist __pycache__ (
    rmdir /s /q __pycache__
)
mkdir dist
echo.

REM PyInstallerでビルド
echo [3/5] PyInstallerでスタンドアロン実行ファイルをビルド中...
echo (これには数分～数十分かかる場合があります)
pyinstaller build.spec
if %errorLevel% neq 0 (
    echo [エラー] PyInstallerのビルドに失敗しました
    echo ビルド出力を確認してください
    pause
    exit /b 1
)
echo.

REM アイコンをコピー
echo [4/5] リソースファイルをコピー中...
copy icon.ico dist\ >nul 2>&1
copy LICENSE dist\KotobaTranscriber\ >nul 2>&1
echo.

REM NSISでインストーラーを作成
echo [5/5] NSISインストーラーを作成中...
makensis /DPRODUCT_VERSION="2.1.0" installer.nsi
if %errorLevel% neq 0 (
    echo [エラー] NSISインストーラーの作成に失敗しました
    pause
    exit /b 1
)
echo.

echo ========================================
echo インストーラーの作成が完了しました！
echo ========================================
echo.
echo 生成されたファイル:
echo   %CD%\dist\KotobaTranscriber-installer.exe
echo.
echo 次のステップ:
echo   1. インストーラーをテスト実行
echo   2. アンインストーラーの動作確認
echo   3. 配布用にアップロード
echo.
pause
