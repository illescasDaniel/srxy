@echo off
setlocal
REM Prefer pwsh when available (faster); fall back to Windows PowerShell 5.1.
where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
	pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-win.ps1" %*
	exit /b %ERRORLEVEL%
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-win.ps1" %*
exit /b %ERRORLEVEL%
