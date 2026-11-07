# Build the Windows portable folder and, when Inno Setup is installed, the installer.
# Run from any directory:  powershell -ExecutionPolicy Bypass -File windows\build.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install -r requirements-windows.txt -r requirements-dev.txt "pyinstaller>=6.0"
python -m pytest -q
pyinstaller --noconfirm --clean windows\currycaster.spec

$env:QT_QPA_PLATFORM = "offscreen"
& .\dist\Currycaster\Currycaster.exe --self-check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& .\dist\Currycaster\Currycaster.exe --smoke
if ($LASTEXITCODE -ne 0) {
    Write-Host "Smoke failed. See %APPDATA%\currycaster\startup.log and smoke-result.txt"
    exit $LASTEXITCODE
}

$Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $Iscc) {
    & $Iscc windows\installer.iss
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "Installer: windows\output\Currycaster-Setup.exe"
} else {
    Write-Host "Inno Setup 6 was not found. Portable build: dist\Currycaster\Currycaster.exe"
}
