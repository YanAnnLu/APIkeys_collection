param(
    [string]$Python = "py",
    [string]$ReportPath = "state\heartbeat\heartbeat.md",
    [string]$PlanJsonPath = "state\heartbeat\heartbeat_plan.json",
    [switch]$SkipCi
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

$env:PYTHONDONTWRITEBYTECODE = "1"

$ReportParent = Split-Path -Parent $ReportPath
if ($ReportParent) {
    New-Item -ItemType Directory -Force $ReportParent | Out-Null
}

$cliArgs = @(
    "-B",
    "APIkeys_collection.py",
    "--heartbeat-report", $ReportPath,
    "--write-heartbeat-plan-json", $PlanJsonPath
)
if ($SkipCi) {
    $cliArgs += "--heartbeat-skip-ci"
}

& $Python @cliArgs

$status = git status --short --branch
Write-Host "[heartbeat] git status"
$status | ForEach-Object { Write-Host $_ }

Write-Host "[heartbeat] report: $ReportPath"
Write-Host "[heartbeat] plan:   $PlanJsonPath"
