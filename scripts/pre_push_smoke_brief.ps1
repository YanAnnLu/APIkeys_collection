param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ForwardArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$CleanForwardArgs = @($ForwardArgs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

if ($CleanForwardArgs | Where-Object { $_ -in @("-Help", "--help", "-?", "/?", "/h") }) {
    Write-Host "Usage: scripts\pre_push_smoke_brief.ps1 [pre_push_smoke.ps1 options]"
    Write-Host ""
    Write-Host "Runs the full pre-push smoke suite and writes a summarized log under state/logs."
    Write-Host ""
    Write-Host "Common options forwarded to pre_push_smoke.ps1:"
    Write-Host "  -SkipTests       Skip unittest discovery."
    Write-Host "  -SkipSummary     Skip CLI summary."
    Write-Host "  -SkipDiffCheck   Skip git diff --check checks."
    Write-Host "  -SkipMvpSmoke    Skip MVP demo offline smoke."
    Write-Host "  -Python <cmd>    Python launcher command, default: py."
    exit 0
}

$LogDir = Join-Path $ProjectRoot "state/logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "pre_push_smoke_$Stamp.log"
$StdoutPath = "$LogPath.stdout"
$StderrPath = "$LogPath.stderr"
$PrePushScript = Join-Path $ScriptDir "pre_push_smoke.ps1"

Write-Host "[pre-push-smoke-brief] writing full log to $LogPath"

$ExitCode = 0
try {
    $ProcessArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $PrePushScript
    ) + $CleanForwardArgs
    $Process = Start-Process -FilePath "powershell.exe" `
        -ArgumentList $ProcessArgs `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath
    $ExitCode = $Process.ExitCode
    if (Test-Path -LiteralPath $StdoutPath) {
        Get-Content -LiteralPath $StdoutPath | Set-Content -LiteralPath $LogPath
    }
    if (Test-Path -LiteralPath $StderrPath) {
        Get-Content -LiteralPath $StderrPath | Add-Content -LiteralPath $LogPath
    }
} catch {
    $ExitCode = 1
    $_ | Out-String | Add-Content -LiteralPath $LogPath
} finally {
    Remove-Item -LiteralPath $StdoutPath, $StderrPath -ErrorAction SilentlyContinue
}

$BriefScript = Join-Path $ScriptDir "summarize_command_log.ps1"
& $BriefScript -LogPath $LogPath -ExitCode $ExitCode
exit $ExitCode
