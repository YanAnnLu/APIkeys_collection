param(
    [string]$Python = "py",
    [string]$ReportPath = "state\heartbeat\heartbeat.md",
    [string]$PlanJsonPath = "state\heartbeat\heartbeat_plan.json",
    [string]$AgentPromptPath = "state\heartbeat\agent_prompt.md",
    [switch]$SkipCi,
    [switch]$RunAgent,
    [string]$AgentExecutable = "",
    [string[]]$AgentArguments = @()
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
    "--write-heartbeat-plan-json", $PlanJsonPath,
    "--heartbeat-agent-prompt", $AgentPromptPath
)
if ($SkipCi) {
    $cliArgs += "--heartbeat-skip-ci"
}

& $Python @cliArgs

$plan = Get-Content -Raw -Path $PlanJsonPath | ConvertFrom-Json
$safe = [bool]$plan.recommended_plan.safe_to_progress

if (-not $safe) {
    Write-Host "[heartbeat-agent] safe_to_progress=false; no agent invoked."
    Write-Host "[heartbeat-agent] report: $ReportPath"
    Write-Host "[heartbeat-agent] plan:   $PlanJsonPath"
    exit 0
}

Write-Host "[heartbeat-agent] safe_to_progress=true"
Write-Host "[heartbeat-agent] prompt: $AgentPromptPath"

if (-not $RunAgent) {
    Write-Host "[heartbeat-agent] dry run only. Re-run with -RunAgent and -AgentExecutable to invoke an external agent."
    exit 0
}

if (-not $AgentExecutable) {
    Write-Error "[heartbeat-agent] -RunAgent requires -AgentExecutable."
    exit 2
}

Write-Host "[heartbeat-agent] invoking external agent: $AgentExecutable"
& $AgentExecutable @AgentArguments $AgentPromptPath
exit $LASTEXITCODE
