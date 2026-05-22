param(
    [string] $Python = "py",
    [switch] $SkipTests,
    [switch] $SkipSummary,
    [switch] $SkipDiffCheck
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

# Git hook 會在不同 shell 裡啟動；先固定 pycache 位置，避免 Windows/RaiDrive 鎖住 repo 內 __pycache__。
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "apikeys_collection_pycache"
$env:PYTHONDONTWRITEBYTECODE = "1"

Write-Host "[pre-push-smoke] repository: $ProjectRoot"
Write-Host "[pre-push-smoke] python:     $Python"

if (-not $SkipDiffCheck) {
    Write-Host "[pre-push-smoke] git diff --check"
    git diff --check
}

Write-Host "[pre-push-smoke] py_compile core entrypoints"
& $Python -B -m py_compile `
    APIkeys_collection.py `
    APIkeys_collection_ui.py `
    frontends\tk\launcher_ui.py `
    api_launcher\core.py

if (-not $SkipTests) {
    Write-Host "[pre-push-smoke] unittest discover -s tests"
    & $Python -B -m unittest discover -s tests
}

if (-not $SkipSummary) {
    Write-Host "[pre-push-smoke] CLI summary"
    & $Python -B APIkeys_collection.py --summary
}

Write-Host "[pre-push-smoke] OK"
