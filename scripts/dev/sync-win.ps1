#Requires -Version 5.1
<#
.SYNOPSIS
  Windows developer sync: uv extras + CUDA PyTorch when an NVIDIA GPU is present.

.DESCRIPTION
  `uv sync --extra semantic --extra windows` alone leaves (or restores) CPU-only torch.
  Always use this wrapper on Windows GPU machines instead of bare `uv sync`.
#>
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $repoRoot

Write-Host 'sync-win: uv sync --extra semantic --extra windows'
& uv sync --extra semantic --extra windows
if ($LASTEXITCODE -ne 0) {
	exit $LASTEXITCODE
}

& (Join-Path $PSScriptRoot 'ensure-windows-cuda-torch.ps1')
exit $LASTEXITCODE
