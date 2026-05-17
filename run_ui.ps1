$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPath = Join-Path $env:LOCALAPPDATA "APIkeys_collection\venv-py313"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

if (Test-Path $PythonExe) {
    & $PythonExe APIkeys_collection_ui.py
} else {
    py APIkeys_collection_ui.py
}
