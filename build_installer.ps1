# KotobaTranscriber Installer Builder (PowerShell version)
# PyInstallerとNSISを使用して配布用インストーラーを作成

param(
    [switch]$SkipNSIS = $false,
    [string]$Version = "2.1.0"
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [ValidateSet("Info", "Warning", "Error", "Success")]$Type = "Info")
    $colors = @{
        "Info"    = "Cyan"
        "Warning" = "Yellow"
        "Error"   = "Red"
        "Success" = "Green"
    }
    Write-Host $Message -ForegroundColor $colors[$Type]
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KotobaTranscriber Installer Builder v2.1" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 前提条件チェック
Write-Status "[1/5] 前提条件をチェック中..." "Info"

# PyInstallerチェック
try {
    $pyinst = pyinstaller --version 2>$null
    Write-Status "PyInstaller: OK" "Success"
} catch {
    Write-Status "PyInstallerがインストールされていません" "Error"
    Write-Status "実行: pip install pyinstaller" "Info"
    exit 1
}

# NSISチェック
if (-not $SkipNSIS) {
    try {
        $makensis = Get-Command makensis -ErrorAction Stop
        Write-Status "NSIS: OK" "Success"
    } catch {
        Write-Status "NSISがインストールされていません" "Warning"
        Write-Status "ダウンロード: https://nsis.sourceforge.io" "Info"
        $SkipNSIS = $true
    }
}
Write-Host ""

# distディレクトリのクリア
Write-Status "[2/5] 前回のビルドをクリア中..." "Info"
@("dist", "build", "__pycache__") | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item -Path $_ -Recurse -Force
    }
}
New-Item -ItemType Directory -Path "dist" -Force | Out-Null
Write-Host ""

# PyInstallerでビルド
Write-Status "[3/5] PyInstallerでスタンドアロン実行ファイルをビルド中..." "Info"
Write-Status "(これには数分～数十分かかる場合があります)" "Warning"

& pyinstaller build.spec
if ($LASTEXITCODE -ne 0) {
    Write-Status "PyInstallerのビルドに失敗しました" "Error"
    exit 1
}
Write-Host ""

# リソースをコピー
Write-Status "[4/5] リソースファイルをコピー中..." "Info"
Copy-Item -Path "icon.ico" -Destination "dist\" -Force -ErrorAction SilentlyContinue
Copy-Item -Path "LICENSE" -Destination "dist\KotobaTranscriber\" -Force -ErrorAction SilentlyContinue
Write-Host ""

# NSISでインストーラーを作成
if (-not $SkipNSIS) {
    Write-Status "[5/5] NSISインストーラーを作成中..." "Info"
    & makensis /DPRODUCT_VERSION="$Version" installer.nsi
    if ($LASTEXITCODE -ne 0) {
        Write-Status "NSISインストーラーの作成に失敗しました" "Error"
        exit 1
    }
} else {
    Write-Status "[5/5] NSISをスキップしました" "Warning"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Status "インストーラーの作成が完了しました！" "Success"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

if (-not $SkipNSIS) {
    Write-Status "生成されたファイル:" "Info"
    Write-Host "  $(Get-Location)\dist\KotobaTranscriber-installer.exe"
} else {
    Write-Status "生成されたポータブル実行ファイル:" "Info"
    Write-Host "  $(Get-Location)\dist\KotobaTranscriber\KotobaTranscriber.exe"
}

Write-Host ""
Write-Status "次のステップ:" "Info"
Write-Host "  1. インストーラーをテスト実行"
Write-Host "  2. アンインストーラーの動作確認"
Write-Host "  3. 配布用にアップロード"
