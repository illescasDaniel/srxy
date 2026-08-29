#Requires -Version 5.1
<#
.SYNOPSIS
  Windows developer sync: uv extras + CUDA PyTorch when an NVIDIA GPU is present.

.DESCRIPTION
  On NVIDIA machines, syncs with --extra semantic-gpu so uv installs CUDA torch
  from the pytorch-cu130 index (see [tool.uv.sources] in pyproject.toml) instead
  of the CPU-only PyPI wheel. Without a GPU, uses --extra semantic as before.
  Always runs ensure-windows-cuda-torch.ps1 afterward as a safety net.
#>
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $repoRoot

function Test-NvidiaGpuPresent {
	if ($env:SRXY_SKIP_CUDA_TORCH -eq '1') {
		return $false
	}
	# Empty CUDA_VISIBLE_DEVICES is the project's documented CPU-force for gates;
	# do not select semantic-gpu in that mode.
	if ($null -ne $env:CUDA_VISIBLE_DEVICES -and $env:CUDA_VISIBLE_DEVICES.Trim() -eq '') {
		return $false
	}
	$smi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
	if (-not $smi) {
		return $false
	}
	$p = Start-Process -FilePath $smi.Source -ArgumentList @('-L') -NoNewWindow -PassThru -Wait `
		-RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) `
		-RedirectStandardError ([System.IO.Path]::GetTempFileName())
	return ($p.ExitCode -eq 0)
}

if (Test-NvidiaGpuPresent) {
	Write-Host 'sync-win: uv sync --extra semantic-gpu --extra windows'
	& uv sync --extra semantic-gpu --extra windows
} else {
	Write-Host 'sync-win: uv sync --extra semantic --extra windows'
	& uv sync --extra semantic --extra windows
}
if ($LASTEXITCODE -ne 0) {
	exit $LASTEXITCODE
}

& (Join-Path $PSScriptRoot 'ensure-windows-cuda-torch.ps1')
exit $LASTEXITCODE
