param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ForwardArgs
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$LogDir = Join-Path $ProjectRoot "state/logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "pre_push_smoke_$Stamp.log"
$StdoutPath = "$LogPath.stdout"
$StderrPath = "$LogPath.stderr"
$PrePushScript = Join-Path $ScriptDir "pre_push_smoke.ps1"
$CleanForwardArgs = @($ForwardArgs | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

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
