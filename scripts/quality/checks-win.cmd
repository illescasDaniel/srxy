@echo off
REM Prefer PowerShell 7 (pwsh) when available; fall back to Windows PowerShell 5.1.
where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
	pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0checks-win.ps1" %*
) else (
	powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0checks-win.ps1" %*
)
exit /b %ERRORLEVEL%
