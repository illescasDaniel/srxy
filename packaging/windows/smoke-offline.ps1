#Requires -Version 5.1
<#
.SYNOPSIS
  Smoke-test the built Windows PySide offline fat SrxyInstaller.exe.

.DESCRIPTION
  Without -InstallerExe: locates dist\windows-pyside-installer-stage\SrxyInstaller.exe
  from a prior build-offline-pyside.ps1 run (falls back to unzipping the latest
  dist\srxy-*-installer-*-pyside-x86_64.zip). Relocates a copy of the fat exe to
  a temp directory first (same relocation-bug class as packaging/macos/smoke-offline.sh),
  then drives a full headless install + uninstall through the SFX (extracts the
  embedded python\ + venv\ + share\ on first launch).

.PARAMETER InstallerExe
  Path to a built fat SrxyInstaller.exe (defaults to the latest local build).
#>
param(
	[string]$InstallerExe = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Resolve-FatInstaller {
	param([string]$Preferred)
	if ($Preferred) {
		if (-not (Test-Path -LiteralPath $Preferred)) {
			throw "installer not found: $Preferred"
		}
		return (Resolve-Path -LiteralPath $Preferred).Path
	}
	$staged = Join-Path $Root "dist\windows-pyside-installer-stage\SrxyInstaller.exe"
	if (Test-Path -LiteralPath $staged) {
		return (Resolve-Path -LiteralPath $staged).Path
	}
	$zips = @(Get-ChildItem -LiteralPath (Join-Path $Root "dist") -Filter "srxy-*-installer-*-pyside-x86_64.zip" -ErrorAction SilentlyContinue |
		Sort-Object LastWriteTime -Descending)
	if ($zips.Count -eq 0) {
		throw "fat SrxyInstaller.exe not found (run build-offline-pyside.ps1 first, or pass -InstallerExe)"
	}
	$extractDir = Join-Path $env:TEMP ("srxy-pyside-zip-" + [guid]::NewGuid().ToString("n"))
	New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
	Expand-Archive -LiteralPath $zips[0].FullName -DestinationPath $extractDir -Force
	$exe = Get-ChildItem -LiteralPath $extractDir -Filter "SrxyInstaller.exe" -Recurse | Select-Object -First 1
	if (-not $exe) {
		throw "zip $($zips[0].Name) did not contain SrxyInstaller.exe"
	}
	return $exe.FullName
}

$BuiltExe = Resolve-FatInstaller -Preferred $InstallerExe

# Relocate before smoke-testing: the SFX must work when the exe alone is copied
# elsewhere (the distribution zip contains only this file).
$StageDir = Join-Path $env:TEMP ("srxy-pyside-smoke-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
$SmokeExe = Join-Path $StageDir "SrxyInstaller.exe"
Copy-Item -LiteralPath $BuiltExe -Destination $SmokeExe -Force
Write-Host "Smoke-testing relocated fat installer: $SmokeExe (built at $BuiltExe)"

try {
	Write-Host "Headless install/uninstall through fat SrxyInstaller.exe..."
	$Prefix = Join-Path $StageDir "prefix"
	# Privacy ack version is embedded in the payload; ask the staged wizard venv if
	# present, otherwise the fat exe --help path still needs a valid ack — read from
	# the checkout via uv as a stable fallback (same constant the build smoke uses).
	$ack = (
		uv run --directory $Root python -c "from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION; print(PRIVACY_NOTICE_VERSION)"
	).Trim()
	$install = Start-Process -FilePath $SmokeExe -ArgumentList @(
		"--install", "--prefix", $Prefix, "--privacy-ack", $ack, "--confirm-unsafe", "--no-add-path"
	) -Wait -PassThru -NoNewWindow
	if ($install.ExitCode -ne 0) {
		throw "headless install via fat SrxyInstaller.exe failed (exit $($install.ExitCode))"
	}
	$GuiExe = Join-Path $Prefix "bin\Srxy.exe"
	$CliLauncher = Join-Path $Prefix "bin\srxy.cmd"
	if (-not (Test-Path -LiteralPath $GuiExe)) {
		throw "GUI launcher missing after install: $GuiExe"
	}
	if (-not (Test-Path -LiteralPath $CliLauncher)) {
		throw "CLI launcher missing after install: $CliLauncher"
	}
	& $CliLauncher --version
	if ($LASTEXITCODE -ne 0) {
		throw "srxy --version via launcher failed"
	}
	$uninstall = Start-Process -FilePath $SmokeExe -ArgumentList @(
		"--uninstall", "--prefix", $Prefix, "--confirm-unsafe"
	) -Wait -PassThru -NoNewWindow
	if ($uninstall.ExitCode -ne 0) {
		throw "headless uninstall via fat SrxyInstaller.exe failed (exit $($uninstall.ExitCode))"
	}
	if (Test-Path -LiteralPath $Prefix) {
		throw "prefix still exists after uninstall: $Prefix"
	}

	Write-Host "PySide offline fat installer smoke OK: $SmokeExe"
}
finally {
	Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
}
