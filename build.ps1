$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    py -3.12 -m venv (Join-Path $ProjectRoot ".venv")
}

& $PythonPath -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
& $PythonPath -m pip install -r (Join-Path $ProjectRoot "requirements-build.txt")
& $PythonPath (Join-Path $ProjectRoot "scripts\build_icon.py")
& $PythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    (Join-Path $ProjectRoot "CatType.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$Executable = Join-Path $ProjectRoot "dist\Cat Type.exe"
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Build completed without producing $Executable"
}

Get-Item -LiteralPath $Executable

$InnoCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)
$InnoCompiler = $InnoCandidates |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1

if ($InnoCompiler) {
    & $InnoCompiler (Join-Path $ProjectRoot "packaging\CatType.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE"
    }
    $Installer = Join-Path $ProjectRoot "dist\Cat Type Setup.exe"
    if (-not (Test-Path -LiteralPath $Installer)) {
        throw "Installer build completed without producing $Installer"
    }
    Get-Item -LiteralPath $Installer
} else {
    Write-Warning "Inno Setup 6 was not found; skipped the installer build."
}
