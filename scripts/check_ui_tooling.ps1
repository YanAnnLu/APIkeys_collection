param(
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$userProfile = [Environment]::GetFolderPath('UserProfile')
$localAppData = [Environment]::GetFolderPath('LocalApplicationData')
if (-not $userProfile) {
    $userProfile = $env:USERPROFILE
}
if (-not $userProfile) {
    $userProfile = $HOME
}
if (-not $localAppData) {
    $localAppData = $env:LOCALAPPDATA
}

function Resolve-FirstExistingPath {
    param([string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Resolve-CommandSource {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            if ($command.Source) {
                return $command.Source
            }
            if ($command.Path) {
                return $command.Path
            }
        }
    }
    return $null
}

function Invoke-VersionProbe {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    if (-not $Executable) {
        return ''
    }
    try {
        # 版本探測只呼叫明確的 --version 類參數；不要啟動 GUI，也不要修改本機設定。
        $output = & $Executable @Arguments 2>&1
        $line = $output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1
        $version = (($line) -as [string]).Trim()
        if (-not [string]::IsNullOrWhiteSpace($version)) {
            return $version
        }
    } catch {
    }

    try {
        # Electron/Qt GUI 工具有時不在非互動 shell 輸出版本；檔案版本資訊可作為只讀 fallback。
        $versionInfo = (Get-Item -LiteralPath $Executable).VersionInfo
        if (-not [string]::IsNullOrWhiteSpace($versionInfo.ProductVersion)) {
            return $versionInfo.ProductVersion
        }
        if (-not [string]::IsNullOrWhiteSpace($versionInfo.FileVersion)) {
            return $versionInfo.FileVersion
        }
    } catch {
    }

    return ''
}

function Test-CondaEnvHasPySide6 {
    param(
        [string]$CondaExecutable,
        [string]$EnvName
    )

    if (-not $CondaExecutable) {
        return $false
    }
    try {
        $null = & $CondaExecutable run -n $EnvName python -c "import PySide6" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-InstalledAppVersion {
    param([string]$DisplayName)

    $registryRoots = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    foreach ($root in $registryRoots) {
        try {
            $entry = Get-ItemProperty $root -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName -eq $DisplayName } |
                Select-Object -First 1
            if ($entry -and -not [string]::IsNullOrWhiteSpace($entry.DisplayVersion)) {
                return $entry.DisplayVersion
            }
        } catch {
        }
    }
    return ''
}

$spectraPath = Resolve-CommandSource @('spectra', 'spectra.exe')
if (-not $spectraPath) {
    $spectraCandidates = @()
    $spectraCandidates += (Join-Path -Path $localAppData -ChildPath 'Spectra\spectra.exe')
    $spectraCandidates += (Join-Path -Path $userProfile -ChildPath 'Applications\Spectra\spectra.exe')
    $spectraPath = Resolve-FirstExistingPath -Candidates $spectraCandidates
}

$qtCreatorPath = Resolve-CommandSource @('qtcreator', 'qtcreator.exe')
if (-not $qtCreatorPath) {
    $qtCreatorCandidates = @()
    $qtCreatorCandidates += 'C:\Qt\Tools\QtCreator\bin\qtcreator.exe'
    $qtCreatorCandidates += (Join-Path -Path $localAppData -ChildPath 'Programs\Qt Creator\bin\qtcreator.exe')
    $qtCreatorCandidates += (Join-Path -Path $env:ProgramFiles -ChildPath 'Qt Creator\bin\qtcreator.exe')
    $qtCreatorCandidates += (Join-Path -Path ${env:ProgramFiles(x86)} -ChildPath 'Qt Creator\bin\qtcreator.exe')
    $qtCreatorPath = Resolve-FirstExistingPath -Candidates $qtCreatorCandidates
}

$condaPath = Resolve-CommandSource @('conda', 'conda.exe')
if ($condaPath -and -not (Test-Path -LiteralPath $condaPath)) {
    $condaPath = $null
}
if (-not $condaPath) {
    $condaCandidates = @()
    $condaCandidates += (Join-Path -Path $userProfile -ChildPath 'anaconda3\Scripts\conda.exe')
    $condaCandidates += (Join-Path -Path $userProfile -ChildPath 'miniconda3\Scripts\conda.exe')
    $condaCandidates += (Join-Path -Path $userProfile -ChildPath 'mambaforge\Scripts\conda.exe')
    $condaPath = Resolve-FirstExistingPath -Candidates $condaCandidates
}

$condaEnvs = @()
if ($condaPath) {
    # Windows 上 conda.exe 有時在非互動子程序裡不穩定輸出 JSON；用檔案系統列 env 可避免把檢查腳本變成 Conda 啟動相依。
    $condaRoot = $null
    if ($condaPath -match '^(.*)\\Scripts\\conda\.exe$') {
        $condaRoot = $Matches[1]
    }
    if ($condaRoot -and (Test-Path -LiteralPath $condaRoot)) {
        $envRoot = Join-Path $condaRoot 'envs'
        $condaEnvs = @('base')
        if (Test-Path -LiteralPath $envRoot) {
            $condaEnvs += @(Get-ChildItem -LiteralPath $envRoot -Directory | Select-Object -ExpandProperty Name)
        }
    }
}

$pysideChecks = @()
foreach ($envName in @('py3_12_13', 'metal_trade_312')) {
    $pysideChecks += [PSCustomObject]@{
        env = $envName
        exists = $condaEnvs -contains $envName
        has_pyside6 = Test-CondaEnvHasPySide6 -CondaExecutable $condaPath -EnvName $envName
    }
}

$spectraVersion = Invoke-VersionProbe -Executable $spectraPath -Arguments @('--version')
if ([string]::IsNullOrWhiteSpace($spectraVersion)) {
    $spectraVersion = Resolve-InstalledAppVersion -DisplayName 'Spectra'
}

$result = [PSCustomObject]@{
    generated_at = (Get-Date).ToString('s')
    workstation = $env:COMPUTERNAME
    spectra = [PSCustomObject]@{
        path = $spectraPath
        available = [bool]$spectraPath
        version = $spectraVersion
    }
    qt_creator = [PSCustomObject]@{
        path = $qtCreatorPath
        available = [bool]$qtCreatorPath
        version = Invoke-VersionProbe -Executable $qtCreatorPath -Arguments @('-version')
    }
    conda = [PSCustomObject]@{
        path = $condaPath
        available = [bool]$condaPath
        envs = $condaEnvs
        pyside6_checks = $pysideChecks
    }
}

if ($Json) {
    $result | ConvertTo-Json -Depth 6
    exit 0
}

Write-Host "[ui-tooling] Spectra:     $($result.spectra.available) $($result.spectra.version) $($result.spectra.path)"
Write-Host "[ui-tooling] Qt Creator:  $($result.qt_creator.available) $($result.qt_creator.version) $($result.qt_creator.path)"
Write-Host "[ui-tooling] Conda:       $($result.conda.available) $($result.conda.path)"
if ($result.conda.envs.Count -gt 0) {
    Write-Host "[ui-tooling] Conda envs:   $($result.conda.envs -join ', ')"
}
foreach ($check in $result.conda.pyside6_checks) {
    Write-Host "[ui-tooling] PySide6 env=$($check.env) exists=$($check.exists) has_pyside6=$($check.has_pyside6)"
}

if (-not $result.qt_creator.available) {
    Write-Host "[ui-tooling] next: Qt Creator is not installed or not on PATH on this workstation."
}
