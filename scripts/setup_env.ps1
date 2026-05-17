$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$VenvRoot = Join-Path $env:LOCALAPPDATA "APIkeys_collection"
$VenvPath = Join-Path $VenvRoot "venv-py313"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $VenvRoot | Out-Null

if (-not (Test-Path $PythonExe)) {
    py -3.13 -m venv $VenvPath
}

& $PythonExe -m pip install -r requirements-dev.txt
& $PythonExe -m py_compile APIkeys_collection.py APIkeys_collection_ui.py
& $PythonExe APIkeys_collection.py --summary

Write-Host ""
Write-Host "Environment ready."
Write-Host "Virtual environment: $VenvPath"
Write-Host "Activate with: & `"$VenvPath\Scripts\Activate.ps1`""
Write-Host "Run UI with: .\scripts\run_ui.ps1"
