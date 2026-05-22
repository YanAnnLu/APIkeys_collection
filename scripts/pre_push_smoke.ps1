param(
    [string] $Python = "py",
    [switch] $SkipTests,
    [switch] $SkipSummary,
    [switch] $SkipDiffCheck,
    [switch] $SkipMvpSmoke
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
    # 手動執行時要檢查工作區與 staged diff；pre-push hook 則還要檢查已 commit 但尚未推送的範圍。
    $null = $true
    Write-Host "[pre-push-smoke] git diff --check worktree"
    git diff --check
    Write-Host "[pre-push-smoke] git diff --check staged"
    git diff --check --cached
    $upstream = git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $upstream) {
        Write-Host "[pre-push-smoke] git diff --check pending push $upstream..HEAD"
        git diff --check "$upstream..HEAD"
    } else {
        Write-Host "[pre-push-smoke] no upstream branch found; skipped pending-push diff check"
    }
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

if (-not $SkipMvpSmoke) {
    Write-Host "[pre-push-smoke] MVP demo offline smoke"
    $mvpSmokeJson = & $Python -B APIkeys_collection.py `
        --db state/pre_push_mvp_demo/launcher.sqlite `
        --init-db `
        --seed `
        --run-mvp-demo-smoke-json state/pre_push_mvp_demo/flow.json
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    $mvpSmoke = $mvpSmokeJson | ConvertFrom-Json
    if (-not $mvpSmoke.succeeded) {
        throw "MVP demo smoke failed: $mvpSmokeJson"
    }
    Write-Host "[pre-push-smoke] MVP demo smoke stage=$($mvpSmoke.stage) row_count=$($mvpSmoke.row_count)"
}

Write-Host "[pre-push-smoke] OK"
