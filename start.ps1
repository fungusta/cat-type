$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonwPath = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    py -3.12 -m venv (Join-Path $ProjectRoot ".venv")
    & $PythonPath -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
}

Start-Process -FilePath $PythonwPath `
    -ArgumentList (Join-Path $ProjectRoot "cat_type.py") `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden

