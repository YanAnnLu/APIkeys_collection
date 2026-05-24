@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
echo Starting RuRuKa Asset Launcher showcase GUI...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%run_ui.ps1" %*
exit /b %ERRORLEVEL%
