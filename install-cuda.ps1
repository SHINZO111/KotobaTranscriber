# CUDA 12.x Installation Script for KotobaTranscriber
# This script automatically downloads and installs CUDA Toolkit 12.6.3

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CUDA 12.x Toolkit Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check admin privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script requires administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    pause
    exit 1
}

# CUDA 12.6.3 (latest 12.x version)
$cudaVersion = "12.6.3"
$cudaUrl = "https://developer.download.nvidia.com/compute/cuda/12.6.3/network_installers/cuda_12.6.3_windows_network.exe"
$installerPath = "$env:TEMP\cuda_12.6.3_windows_network.exe"

Write-Host "Step 1: Downloading CUDA Toolkit $cudaVersion..." -ForegroundColor Green
Write-Host "URL: $cudaUrl" -ForegroundColor Gray
Write-Host ""

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $cudaUrl -OutFile $installerPath -UseBasicParsing
    $ProgressPreference = 'Continue'

    Write-Host "Download completed: $installerPath" -ForegroundColor Green
    $fileSize = [math]::Round((Get-Item $installerPath).Length / 1MB, 2)
    Write-Host "File size: $fileSize MB" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "ERROR: Download failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Step 2: Installing CUDA Toolkit..." -ForegroundColor Green
Write-Host "Installation mode: Express (recommended)" -ForegroundColor Gray
Write-Host "Estimated time: 5-10 minutes" -ForegroundColor Gray
Write-Host ""
Write-Host "NOTE: Installation window will appear. Please wait until completion." -ForegroundColor Yellow
Write-Host ""

try {
    $installArgs = "-s"
    $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Host "Installation completed successfully!" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Installer returned exit code $($process.ExitCode)" -ForegroundColor Yellow
        Write-Host "Installation may have completed. Continuing verification..." -ForegroundColor Yellow
    }
    Write-Host ""
} catch {
    Write-Host "ERROR: Installation failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    pause
    exit 1
}

Write-Host "Step 3: Verifying installation..." -ForegroundColor Green
Write-Host ""

# Refresh environment variables
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Check nvcc
Write-Host "Checking nvcc:" -ForegroundColor Cyan
try {
    $nvccOutput = & nvcc --version 2>&1
    Write-Host $nvccOutput -ForegroundColor Gray
    Write-Host "SUCCESS: nvcc is working" -ForegroundColor Green
} catch {
    Write-Host "FAILED: nvcc not found" -ForegroundColor Red
    Write-Host "You may need to manually add this to PATH:" -ForegroundColor Yellow
    Write-Host "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin" -ForegroundColor Yellow
}
Write-Host ""

# Check cublas64_12.dll
Write-Host "Searching for cublas64_12.dll:" -ForegroundColor Cyan
$cublasPath = Get-ChildItem -Path "C:\Program Files\NVIDIA GPU Computing Toolkit" -Filter "cublas64_12.dll" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

if ($cublasPath) {
    Write-Host "SUCCESS: Found at $($cublasPath.FullName)" -ForegroundColor Green
} else {
    Write-Host "FAILED: cublas64_12.dll not found" -ForegroundColor Red
    Write-Host "CUDA 12.x installation may be incomplete." -ForegroundColor Yellow
}
Write-Host ""

# Cleanup
Write-Host "Step 4: Cleaning up temporary files..." -ForegroundColor Green
try {
    Remove-Item -Path $installerPath -Force -ErrorAction SilentlyContinue
    Write-Host "Cleanup completed" -ForegroundColor Green
} catch {
    Write-Host "WARNING: Failed to delete temporary file: $installerPath" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Close this PowerShell window" -ForegroundColor White
Write-Host "2. Restart KotobaTranscriber application" -ForegroundColor White
Write-Host "3. Verify GPU acceleration is enabled" -ForegroundColor White
Write-Host ""

pause
