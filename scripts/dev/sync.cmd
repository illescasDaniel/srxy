@echo off
setlocal
REM Platform-aware uv sync (forwards to scripts/dev/sync.py). Prefer: uv run task sync / sync-dev / sync-uploader
where pwsh >nul 2>&1
if %ERRORLEVEL%==0 (
	pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
	exit /b %ERRORLEVEL%
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync.ps1" %*
exit /b %ERRORLEVEL%
