# Build "ACE School Management.exe" — windowed desktop app for taskbar pinning.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Creating application icon..."
if (Test-Path ".venv\Scripts\python.exe") {
    $Python = ".venv\Scripts\python.exe"
} else {
    $Python = "python"
}

& $Python scripts\make_app_icon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Icon = Join-Path $Root "build\ace_school_management.ico"
$Logo = Join-Path $Root "School Logo.jpeg"
$Assets = Join-Path $Root "frontend\assets"

if (-not (Test-Path $Icon)) {
    throw "Icon not found: $Icon"
}

Write-Host "Building ACE School Management.exe with PyInstaller..."
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --name "ACE School Management" `
    --windowed `
    --onefile `
    --icon "$Icon" `
    --paths "$Root" `
    --add-data "$Logo;." `
    --add-data "$Assets;frontend\assets" `
    --hidden-import backend.models.entities `
    --hidden-import sqlalchemy.dialects.sqlite `
    --hidden-import bcrypt `
    --hidden-import PySide6.QtNetwork `
    --collect-submodules reportlab `
  run.py

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Exe = Join-Path $Root "dist\ACE School Management.exe"
if (Test-Path $Exe) {
    Write-Host ""
    Write-Host "Success: $Exe"
    Write-Host "Pin to taskbar: right-click the exe -> Pin to taskbar"
} else {
    throw "Build finished but exe was not found at $Exe"
}
