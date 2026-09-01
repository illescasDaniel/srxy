@echo off
setlocal
REM Platform-aware uv sync (forwards to scripts/dev/sync.py). Bootstrap: uv run --no-project python scripts/dev/sync.py
where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
	pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
	exit /b %ERRORLEVEL%
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
exit /b %ERRORLEVEL%
