param(
    [Parameter(Mandatory = $true)]
    [string] $UserName,

    [Parameter(Mandatory = $true)]
    [string] $UserEmail
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

git config --global user.name $UserName
git config --global user.email $UserEmail
git config --global init.defaultBranch main
git config core.autocrlf false
git config core.eol lf

Write-Host "Git identity configured:"
git config --global --get user.name
git config --global --get user.email
git status --short --branch
