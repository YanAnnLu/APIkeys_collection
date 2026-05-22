param(
    [Parameter(Mandatory = $true)]
    [string] $LogPath,
    [int] $ExitCode = 0,
    [int] $TailLines = 80,
    [int] $MaxKeyLines = 160
)

$ErrorActionPreference = "Stop"

$ResolvedLogPath = Resolve-Path -LiteralPath $LogPath
$Lines = Get-Content -LiteralPath $ResolvedLogPath

$Patterns = @(
    '^\[pre-push-smoke\]',
    '^Ran \d+ tests',
    '^OK\b',
    '^FAILED\b',
    '^ERROR:',
    '^FAIL:',
    'Traceback',
    'AssertionError',
    'UnicodeEncodeError',
    'PermissionError',
    'WinError',
    '\bFAILED\b',
    '\bERROR\b',
    '\bFAIL\b',
    'skipped',
    'MVP demo smoke'
)

$KeyLines = New-Object System.Collections.Generic.List[string]
foreach ($Line in $Lines) {
    foreach ($Pattern in $Patterns) {
        if ($Line -match $Pattern) {
            $KeyLines.Add($Line)
            break
        }
    }
}

Write-Host "[log-brief] log: $ResolvedLogPath"
Write-Host "[log-brief] exit_code: $ExitCode"

if ($KeyLines.Count -gt 0) {
    Write-Host "[log-brief] key_lines:"
    $Start = [Math]::Max(0, $KeyLines.Count - $MaxKeyLines)
    for ($Index = $Start; $Index -lt $KeyLines.Count; $Index++) {
        Write-Host $KeyLines[$Index]
    }
} else {
    Write-Host "[log-brief] no key lines matched; showing final lines"
    $Lines | Select-Object -Last ([Math]::Min($TailLines, $Lines.Count))
}

if ($ExitCode -ne 0) {
    Write-Host "[log-brief] failure_tail:"
    $Lines | Select-Object -Last ([Math]::Min($TailLines, $Lines.Count))
}
