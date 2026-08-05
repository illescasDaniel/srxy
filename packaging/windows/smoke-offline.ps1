#Requires -Version 5.1
<#
.SYNOPSIS
  Smoke-test the Windows offline installer payload / headless engine.

.DESCRIPTION
  Without -InstallerExe: runs the headless CLI against a temp prefix using the
  current checkout (uv run). With -InstallerExe: silent-installs, checks the
  launcher, then uninstalls via the generated uninstaller when present.
#>
param(
	[string]$InstallerExe = "",
	[string]$Prefix = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Get-PrivacyVersion {
	$out = & uv run python -c "from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION; print(PRIVACY_NOTICE_VERSION)"
	return $out.Trim()
}

Push-Location $Root
try {
	if (-not $Prefix) {
		$Prefix = Join-Path $env:TEMP ("srxy-smoke-" + [guid]::NewGuid().ToString("n"))
	}

	if ($InstallerExe) {
		if (-not (Test-Path -LiteralPath $InstallerExe)) {
			throw "installer not found: $InstallerExe"
		}
		Write-Host "Silent install: $InstallerExe -> $Prefix"
		$ack = Get-PrivacyVersion
		$setupLog = "$Prefix-setup.log"
		# Components: core only for a fast smoke (no vendor downloads).
		# Start-Process -Wait is required: Inno re-launches itself and the first
		# process can exit before CurStepChanged / the install engine finishes.
		$args = @(
			"/VERYSILENT",
			"/SUPPRESSMSGBOXES",
			"/NORESTART",
			"/DIR=$Prefix",
			"/COMPONENTS=core",
			"/TASKS=!",
			"/LOG=$setupLog"
		)
		$proc = Start-Process -FilePath $InstallerExe -ArgumentList $args -PassThru -Wait
		if ($proc.ExitCode -ne 0) {
			throw "silent installer failed: $($proc.ExitCode)"
		}
		$GuiExe = Join-Path $Prefix "bin\Srxy.exe"
		$CmdLauncher = Join-Path $Prefix "bin\srxy.cmd"
		if (-not (Test-Path -LiteralPath $GuiExe)) {
			$engineLog = Join-Path $Prefix "logs\installer-engine.log"
			if (Test-Path -LiteralPath $engineLog) {
				Write-Host "----- installer-engine.log -----"
				Get-Content -LiteralPath $engineLog
			}
			throw "GUI launcher missing after install: $GuiExe"
		}
		if (-not (Test-Path -LiteralPath $CmdLauncher)) {
			throw "CLI launcher missing after install: $CmdLauncher"
		}
		& $CmdLauncher --version
		if ($LASTEXITCODE -ne 0) {
			throw "srxy --version via launcher failed"
		}
		$Unins = Get-ChildItem -LiteralPath $Prefix -Filter "unins*.exe" -ErrorAction SilentlyContinue |
			Select-Object -First 1
		if ($Unins) {
			Write-Host "Running uninstaller $($Unins.FullName)"
			& $Unins.FullName /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
		}
		else {
			Write-Host "No Inno uninstaller found; removing prefix manually"
			if (Test-Path -LiteralPath $Prefix) {
				Remove-Item -LiteralPath $Prefix -Recurse -Force
			}
		}
		Write-Host "Installer smoke OK"
		return
	}

	Write-Host "Headless CLI smoke into $Prefix"
	$ack = Get-PrivacyVersion
	& uv run python -m srxy.adapters.inbound.installer `
		--install `
		--prefix $Prefix `
		--privacy-ack $ack `
		--confirm-unsafe `
		--no-add-path
	if ($LASTEXITCODE -ne 0) {
		throw "headless install failed"
	}
	$GuiExe = Join-Path $Prefix "bin\Srxy.exe"
	$Launcher = Join-Path $Prefix "bin\srxy.cmd"
	if (-not (Test-Path -LiteralPath $GuiExe)) {
		throw "GUI launcher missing: $GuiExe"
	}
	if (-not (Test-Path -LiteralPath $Launcher)) {
		throw "launcher missing: $Launcher"
	}
	& $Launcher --version
	if ($LASTEXITCODE -ne 0) {
		throw "launcher --version failed"
	}
	& uv run python -m srxy.adapters.inbound.installer `
		--uninstall `
		--prefix $Prefix `
		--confirm-unsafe
	if ($LASTEXITCODE -ne 0) {
		throw "headless uninstall failed"
	}
	if (Test-Path -LiteralPath $Prefix) {
		throw "prefix still exists after uninstall: $Prefix"
	}
	Write-Host "Headless smoke OK"
}
finally {
	Pop-Location
}
