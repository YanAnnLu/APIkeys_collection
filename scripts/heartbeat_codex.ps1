param(
    [string]$Python = "py",
    [string]$CodexExecutable = "codex",
    [string]$ReportPath = "state\heartbeat\heartbeat.md",
    [string]$PlanJsonPath = "state\heartbeat\heartbeat_plan.json",
    [string]$AgentPromptPath = "state\heartbeat\agent_prompt.md",
    [string]$CodexLogPath = "state\heartbeat\codex_run.log",
    [string]$CodexLastMessagePath = "state\heartbeat\codex_last_message.md",
    [string]$Sandbox = "danger-full-access",
    [string]$ApprovalPolicy = "never",
    [string]$Model = "",
    [switch]$SkipCi,
    [switch]$DryRun
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
$CodexLogParent = Split-Path -Parent $CodexLogPath
if ($CodexLogParent) {
    New-Item -ItemType Directory -Force $CodexLogParent | Out-Null
}
$CodexMessageParent = Split-Path -Parent $CodexLastMessagePath
if ($CodexMessageParent) {
    New-Item -ItemType Directory -Force $CodexMessageParent | Out-Null
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
    Write-Host "[heartbeat-codex] safe_to_progress=false; Codex was not invoked."
    Write-Host "[heartbeat-codex] report: $ReportPath"
    Write-Host "[heartbeat-codex] plan:   $PlanJsonPath"
    exit 0
}

$codexArgs = @(
    "exec",
    "--cd", [string]$ProjectRoot,
    "--sandbox", $Sandbox,
    "--ask-for-approval", $ApprovalPolicy,
    "--output-last-message", $CodexLastMessagePath
)
if ($Model) {
    $codexArgs += @("--model", $Model)
}
$codexArgs += "-"

Write-Host "[heartbeat-codex] safe_to_progress=true"
Write-Host "[heartbeat-codex] prompt: $AgentPromptPath"
Write-Host "[heartbeat-codex] log:    $CodexLogPath"
Write-Host "[heartbeat-codex] final:  $CodexLastMessagePath"
Write-Host "[heartbeat-codex] command: $CodexExecutable $($codexArgs -join ' ')"

if ($DryRun) {
    Write-Host "[heartbeat-codex] dry run only; Codex was not invoked."
    exit 0
}

$prompt = Get-Content -Raw -Path $AgentPromptPath
$prompt | & $CodexExecutable @codexArgs 2>&1 | Tee-Object -FilePath $CodexLogPath
exit $LASTEXITCODE
