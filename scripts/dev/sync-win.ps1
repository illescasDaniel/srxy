#Requires -Version 5.1
<#
.SYNOPSIS
  Windows alias for ``uv run task sync-dev`` (``python scripts/dev/sync.py --dev``).

.DESCRIPTION
  Kept so existing ``uv run task sync-win`` / ``sync-win.cmd`` keep working.
  Prefer ``uv run task sync-dev``. Extra arguments are forwarded to sync.py.
#>
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'sync.ps1') --dev @args
exit $LASTEXITCODE
