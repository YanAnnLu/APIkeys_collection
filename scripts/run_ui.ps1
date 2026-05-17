$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$VenvPath = Join-Path $env:LOCALAPPDATA "APIkeys_collection\venv-py313"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"

if (Test-Path $PythonExe) {
    $BasePython = & $PythonExe -c "import sys; print(sys.base_prefix)"
    if (Test-Path (Join-Path $BasePython "tcl\tcl8.6\init.tcl")) {
        $env:TCL_LIBRARY = Join-Path $BasePython "tcl\tcl8.6"
        $env:TK_LIBRARY = Join-Path $BasePython "tcl\tk8.6"
    }
    & $PythonExe APIkeys_collection_ui.py
} else {
    py APIkeys_collection_ui.py
}
