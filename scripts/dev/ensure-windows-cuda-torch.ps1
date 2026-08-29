#Requires -Version 5.1
<#
.SYNOPSIS
  Ensure .venv has a CUDA PyTorch build when an NVIDIA GPU is present.

.DESCRIPTION
  On Windows, bare `uv sync --extra semantic` can leave a CPU-only torch wheel from
  PyPI (or an incomplete stack). Prefer `uv run task sync-win` / `--extra semantic-gpu`
  so the lockfile installs CUDA builds via [tool.uv.sources]. This script is the safety
  net: it detects a CPU-only / broken torch with an NVIDIA GPU present and reinstalls
  torch/torchvision/torchaudio from the PyTorch CUDA index.

  Safe to run repeatedly. No-ops when there is no NVIDIA GPU, when CUDA_VISIBLE_DEVICES
  is intentionally empty for CPU-only experiments, when already on a +cu* build, or when
  SRXY_SKIP_CUDA_TORCH=1.

.PARAMETER CheckOnly
  Report status and exit 2 if a GPU is present but torch is CPU-only; do not install.

.PARAMETER CudaIndex
  PyTorch wheel index tag (default cu130). Use cu126 for older drivers.
#>
param(
	[switch] $CheckOnly,
	[ValidateSet('cu130', 'cu126')]
	[string] $CudaIndex = 'cu130'
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
	$here = $PSScriptRoot
	if ([string]::IsNullOrWhiteSpace($here)) {
		$here = (Get-Location).Path
	}
	return (Resolve-Path -LiteralPath (Join-Path $here '..\..')).Path
}

function Test-NvidiaGpuPresent {
	if ($env:SRXY_SKIP_CUDA_TORCH -eq '1') {
		return $false
	}
	# Empty CUDA_VISIBLE_DEVICES is the project's documented CPU-force for gates;
	# do not rewrite the venv in that mode (torch may still be CUDA-capable).
	if ($null -ne $env:CUDA_VISIBLE_DEVICES -and $env:CUDA_VISIBLE_DEVICES.Trim() -eq '') {
		Write-Host 'ensure-windows-cuda-torch: CUDA_VISIBLE_DEVICES is empty; leaving torch as-is.'
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

function Get-TorchStatus {
	param([string] $PythonExe)
	$code = @'
import torch
print(torch.__version__)
print("1" if torch.cuda.is_available() else "0")
'@
	$out = & $PythonExe -c $code 2>&1
	if ($LASTEXITCODE -ne 0) {
		return @{ Ok = $false; Version = ''; Cuda = $false; Raw = ($out | Out-String) }
	}
	$lines = @($out | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
	$version = if ($lines.Count -ge 1) { $lines[0] } else { '' }
	$cuda = ($lines.Count -ge 2 -and $lines[1] -eq '1')
	return @{ Ok = $true; Version = $version; Cuda = $cuda; Raw = ($out | Out-String) }
}

$repoRoot = Get-RepoRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
	Write-Host "ensure-windows-cuda-torch: missing $python (run uv run task sync-win first)" -ForegroundColor Yellow
	exit 0
}

if (-not (Test-NvidiaGpuPresent)) {
	Write-Host 'ensure-windows-cuda-torch: no NVIDIA GPU (or skip env set); nothing to do.'
	exit 0
}

$status = Get-TorchStatus -PythonExe $python
if (-not $status.Ok) {
	Write-Host "ensure-windows-cuda-torch: could not import torch:$([Environment]::NewLine)$($status.Raw)" -ForegroundColor Yellow
	if ($CheckOnly) { exit 2 }
}
elseif ($status.Version -match '\+cu\d+' -and $status.Cuda) {
	Write-Host ("ensure-windows-cuda-torch: OK ({0}, cuda=True)" -f $status.Version)
	exit 0
}
elseif ($status.Version -match '\+cu\d+' -and -not $status.Cuda) {
	Write-Host ("ensure-windows-cuda-torch: CUDA build present ({0}) but cuda.is_available() is False - check drivers / CUDA_VISIBLE_DEVICES." -f $status.Version) -ForegroundColor Yellow
	exit 0
}

$msg = if ($status.Ok) {
	"CPU-only torch ({0}) with NVIDIA GPU present" -f $status.Version
}
else {
	'torch missing/broken with NVIDIA GPU present'
}

if ($CheckOnly) {
	Write-Host "ensure-windows-cuda-torch: CHECK FAILED - $msg" -ForegroundColor Red
	Write-Host 'Fix: powershell -ExecutionPolicy Bypass -File .\scripts\dev\ensure-windows-cuda-torch.ps1'
	Write-Host 'Or: uv run task sync-win'
	exit 2
}

Write-Host "ensure-windows-cuda-torch: $msg - installing PyTorch $CudaIndex wheels (about 1-2 GiB first time)..." -ForegroundColor Yellow
$index = "https://download.pytorch.org/whl/$CudaIndex"
Push-Location -LiteralPath $repoRoot
try {
	& uv pip install --reinstall-package torch torch torchvision torchaudio --index-url $index
	if ($LASTEXITCODE -ne 0) {
		Write-Host "ensure-windows-cuda-torch: uv pip install failed (exit $LASTEXITCODE)" -ForegroundColor Red
		exit $LASTEXITCODE
	}
}
finally {
	Pop-Location
}

$after = Get-TorchStatus -PythonExe $python
if (-not $after.Ok -or -not $after.Cuda -or $after.Version -notmatch '\+cu\d+') {
	Write-Host "ensure-windows-cuda-torch: install finished but CUDA still unavailable:$([Environment]::NewLine)$($after.Raw)" -ForegroundColor Red
	Write-Host 'See docs/installation.md (Windows GPU section) and docs/development.md.'
	exit 1
}

Write-Host ("ensure-windows-cuda-torch: installed {0} (cuda=True)" -f $after.Version) -ForegroundColor Green
exit 0
