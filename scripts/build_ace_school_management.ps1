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

$Icon = Join-Path $Root "frontend\assets\ace_school_management.ico"
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
    --add-data "$Assets;frontend\assets" `
    --hidden-import backend.models.entities `
    --hidden-import sqlalchemy.dialects.sqlite `
    --hidden-import bcrypt `
    --hidden-import PySide6.QtNetwork `
    --collect-submodules reportlab `
  run.py

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Exe = Join-Path $Root "dist\ACE School Management.exe"
if (-not (Test-Path $Exe)) {
    throw "Build finished but exe was not found at $Exe"
}

Write-Host ""
Write-Host "Building preloaded client database (faculty + inactive students)..."
& $Python scripts\build_deployment_database.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$DeploymentDir = Join-Path $Root "Deployment"
New-Item -ItemType Directory -Force -Path $DeploymentDir | Out-Null
Copy-Item -Force $Exe (Join-Path $DeploymentDir "ACE School Management.exe")

Write-Host ""
Write-Host "Deployment folder ready:"
Write-Host "  $(Join-Path $DeploymentDir 'ACE School Management.exe')"
Write-Host "  $(Join-Path $DeploymentDir 'data\fee_management.db')"
Write-Host "  $(Join-Path $DeploymentDir 'data\master_key.txt')"
Write-Host ""
Write-Host "On first client launch, the app copies data\ into %LOCALAPPDATA%\ACE School Management\"
