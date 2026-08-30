#Requires -Version 5.1
<#
.SYNOPSIS
  Platform-aware uv sync. See scripts/dev/sync.py.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\dev\sync.ps1 --dev
#>
$ErrorActionPreference = 'Stop'
$syncPy = Join-Path $PSScriptRoot 'sync.py'

function Invoke-SyncPy {
	param([string[]] $PyArgs)
	$python = Get-Command python -ErrorAction SilentlyContinue
	if ($python) {
		& $python.Source $syncPy @PyArgs
		return $LASTEXITCODE
	}
	$uv = Get-Command uv -ErrorAction SilentlyContinue
	if ($uv) {
		& $uv.Source run --no-project python $syncPy @PyArgs
		return $LASTEXITCODE
	}
	Write-Error 'Need python or uv to run scripts/dev/sync.py'
	return 1
}

$code = Invoke-SyncPy -PyArgs @($args)
exit $code
