#Requires -Version 5.1
<#
.SYNOPSIS
  Build the Windows PySide offline installer wrapper (parity with the macOS
  offline .app and Linux offline AppImage wizard).

.DESCRIPTION
  Stages a relocatable managed CPython + a wizard-only venv (PySide6 + srxy
  --no-deps, same policy as macOS/Linux offline) under dist\windows-pyside-installer-stage\payload,
  a full srxy wheel for prefix installs under payload\share\srxy\ (same layout
  SRXY_INSTALLER_PAYLOAD already resolves for the Inno bootstrap — see
  srxy.adapters.inbound.installer.package_spec / meta), a prebuilt app
  launcher + icon under payload\share\srxy\windows\ (reused at prefix-install
  time by install.py's _write_windows_gui_exe), and a small compiled
  SrxyInstaller.exe wrapper at the payload root that launches the PySide
  wizard (python -m srxy.adapters.inbound.installer, no args -> GUI).

  This is an ADDITIONAL offline artifact alongside the existing Inno Setup
  installer (packaging/windows/srxy-offline.iss / build-offline.ps1) — it does
  not replace it. The payload folder is zipped for distribution; wrapping it
  in a single-file NSIS installer is a separate follow-up (out of scope here).

.PARAMETER OutDir
  Output directory (default: dist).

.PARAMETER PythonVersion
  Managed CPython version to bundle (default: 3.12).
#>
param(
	[string]$OutDir = "",
	[string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $OutDir) {
	$OutDir = Join-Path $Root "dist"
}

function Get-Sha256Hex {
	param([Parameter(Mandatory = $true)][string]$Path)
	$sha = [System.Security.Cryptography.SHA256]::Create()
	try {
		$stream = [System.IO.File]::OpenRead($Path)
		try {
			$bytes = $sha.ComputeHash($stream)
		}
		finally {
			$stream.Dispose()
		}
	}
	finally {
		$sha.Dispose()
	}
	return ([BitConverter]::ToString($bytes) -replace "-", "").ToLowerInvariant()
}

function Find-Csc {
	$roots = @(
		(Join-Path $env:WINDIR "Microsoft.NET\Framework64"),
		(Join-Path $env:WINDIR "Microsoft.NET\Framework")
	)
	foreach ($root in $roots) {
		if (-not (Test-Path -LiteralPath $root)) {
			continue
		}
		$versions = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
			Where-Object { $_.Name -like "v*" } |
			Sort-Object Name -Descending
		foreach ($v in $versions) {
			$csc = Join-Path $v.FullName "csc.exe"
			if (Test-Path -LiteralPath $csc) {
				return $csc
			}
		}
	}
	return $null
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
	throw "uv is required to build the Windows PySide offline installer."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Stage = Join-Path $OutDir "windows-pyside-installer-stage"
$Payload = Join-Path $Stage "payload"

if (Test-Path -LiteralPath $Stage) {
	Remove-Item -LiteralPath $Stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $Payload "share\srxy\windows") | Out-Null

Push-Location $Root
try {
	$Version = (uv run python -c "from importlib.metadata import version; print(version('srxy'))").Trim()
	$InstallerVersion = (
		uv run python -c "import tomllib,sys; from pathlib import Path; print(tomllib.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))['installer_version'])" `
			(Join-Path $Root "packaging\installer_meta.toml")
	).Trim()
	$Arch = "x86_64"

	Write-Host "Building srxy wheel for offline payload..."
	$WheelDir = Join-Path $OutDir "windows-pyside-installer-wheels"
	if (Test-Path -LiteralPath $WheelDir) {
		Remove-Item -LiteralPath $WheelDir -Recurse -Force
	}
	New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null
	uv build --wheel --out-dir $WheelDir $Root
	$Wheels = @(Get-ChildItem -LiteralPath $WheelDir -Filter "srxy-*.whl")
	if ($Wheels.Count -ne 1) {
		throw "expected exactly one srxy wheel in $WheelDir"
	}
	$Wheel = $Wheels[0].FullName
	Copy-Item -LiteralPath $Wheel -Destination (Join-Path $Payload "share\srxy\") -Force
	Copy-Item -LiteralPath $Wheel -Destination (Join-Path $Payload "share\srxy\srxy.whl") -Force
	Copy-Item -LiteralPath (Join-Path $Root "packaging\installer_meta.toml") `
		-Destination (Join-Path $Payload "share\srxy\installer_meta.toml") -Force

	Write-Host "Installing managed Python $PythonVersion into payload..."
	$env:UV_PYTHON_PREFERENCE = "only-managed"
	$env:UV_LINK_MODE = "copy"
	$PythonNest = Join-Path $Payload "python-nest"
	New-Item -ItemType Directory -Force -Path $PythonNest | Out-Null
	uv python install $PythonVersion --install-dir $PythonNest --no-bin

	$NestedPython = Get-ChildItem -LiteralPath $PythonNest -Recurse -Filter "python.exe" | Select-Object -First 1
	if (-not $NestedPython) {
		throw "managed python.exe not found under $PythonNest"
	}
	$ManagedRoot = $NestedPython.Directory.FullName

	# Flatten to payload\python\python.exe (+ DLLs/Lib), like the Inno bootstrap stage.
	$StablePythonDir = Join-Path $Payload "python"
	New-Item -ItemType Directory -Force -Path $StablePythonDir | Out-Null
	Copy-Item -Path (Join-Path $ManagedRoot "*") -Destination $StablePythonDir -Recurse -Force
	Remove-Item -LiteralPath $PythonNest -Recurse -Force
	$AppPython = Join-Path $StablePythonDir "python.exe"
	if (-not (Test-Path -LiteralPath $AppPython)) {
		throw "stable python missing at $AppPython"
	}

	Write-Host "Creating relocatable wizard venv (PySide6 + srxy --no-deps)..."
	$Venv = Join-Path $Payload "venv"
	uv venv --python $AppPython --relocatable --link-mode copy $Venv
	$VenvPy = Join-Path $Venv "Scripts\python.exe"
	$VenvPyw = Join-Path $Venv "Scripts\pythonw.exe"
	if (-not (Test-Path -LiteralPath $VenvPy)) {
		throw "venv python missing at $VenvPy"
	}
	if (-not (Test-Path -LiteralPath $VenvPyw)) {
		throw "venv pythonw missing at $VenvPyw"
	}

	uv pip install --python $VenvPy "PySide6>=6.6"
	uv pip install --python $VenvPy --no-deps $Root

	# Relocation guard: copy the payload elsewhere and import the wizard from
	# there. A build-host-relative-but-not-truly-portable venv would still
	# work in place but break once the zip is extracted on a user's machine
	# (mirrors the macOS/Linux offline relocation checks).
	Write-Host "Verifying wizard venv is relocatable..."
	$RelocProbe = Join-Path $OutDir "windows-pyside-reloc-probe"
	if (Test-Path -LiteralPath $RelocProbe) {
		Remove-Item -LiteralPath $RelocProbe -Recurse -Force
	}
	Copy-Item -Path $Payload -Destination (Join-Path $RelocProbe "payload") -Recurse -Force
	$ProbePy = Join-Path $RelocProbe "payload\venv\Scripts\python.exe"
	& $ProbePy -c "import PySide6; from srxy.adapters.inbound.installer.install import InstallOptions; print('wizard-reloc-ok')"
	if ($LASTEXITCODE -ne 0) {
		throw "relocated wizard venv import smoke failed"
	}
	Remove-Item -LiteralPath $RelocProbe -Recurse -Force

	Write-Host "Pruning unused PySide6 / Qt payload..."
	& (Join-Path $PSScriptRoot "prune-pyside.ps1") $Venv

	Write-Host "Smoke-testing pruned wizard imports / QML (offscreen)..."
	$env:QT_QPA_PLATFORM = "offscreen"
	& $VenvPy -c "import srxy.adapters.inbound.installer"
	if ($LASTEXITCODE -ne 0) {
		throw "pruned wizard import smoke failed"
	}
	& $VenvPy -m srxy.adapters.inbound.installer --help | Out-Null
	if ($LASTEXITCODE -ne 0) {
		throw "pruned wizard --help smoke failed"
	}
	$QmlSmoke = @"
import sys
from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
qml = b'''
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
ApplicationWindow {
	visible: false
	width: 100
	height: 100
	FolderDialog {}
}
'''
engine.loadData(QByteArray(qml), QUrl())
if not engine.rootObjects():
	raise SystemExit("pruned QML smoke failed: no root objects")
print("qml smoke OK")
"@
	& $VenvPy -c $QmlSmoke
	if ($LASTEXITCODE -ne 0) {
		throw "pruned QML smoke failed"
	}
	Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue

	Write-Host "Building installer + app icons and prebuilt app launcher..."
	$WinShare = Join-Path $Payload "share\srxy\windows"
	$SetupIco = Join-Path $Stage "srxy-installer.ico"
	$AppIco = Join-Path $WinShare "srxy.ico"
	$AppLauncherExe = Join-Path $WinShare "Srxy.exe"
	$Csc = Find-Csc
	if (-not $Csc) {
		throw "csc.exe not found; install .NET Framework 4.x developer pack tools."
	}
	$IcoAndLauncherScript = @"
from pathlib import Path
import subprocess
import sys
from srxy.adapters.inbound.installer.install import _find_csc, _launcher_cs_source, _write_windows_ico

stage_ico = Path(sys.argv[1])
app_ico = Path(sys.argv[2])
out_exe = Path(sys.argv[3])
_write_windows_ico(stage_ico, installer=True)
_write_windows_ico(app_ico, installer=False)
csc = _find_csc()
cs = _launcher_cs_source()
if csc is None:
    raise SystemExit('csc.exe not found; install .NET Framework 4.x')
cmd = [
    str(csc), '/nologo', '/target:winexe',
    f'/win32icon:{app_ico}',
    '/reference:System.Windows.Forms.dll',
    f'/out:{out_exe}',
    str(cs),
]
subprocess.run(cmd, check=True)
print(f'wrote {out_exe}')
"@
	uv run python -c $IcoAndLauncherScript $SetupIco $AppIco $AppLauncherExe
	if ($LASTEXITCODE -ne 0) {
		throw "app icon / prebuilt app launcher build failed"
	}

	Write-Host "Compiling SrxyInstaller.exe wrapper launcher..."
	$LauncherCs = Join-Path $Root "src\srxy\resources\windows\SrxyInstallerLauncher.cs"
	if (-not (Test-Path -LiteralPath $LauncherCs)) {
		throw "missing $LauncherCs"
	}
	$InstallerExeOut = Join-Path $Payload "SrxyInstaller.exe"
	& $Csc /nologo /target:winexe "/win32icon:$SetupIco" /reference:System.Windows.Forms.dll "/out:$InstallerExeOut" $LauncherCs
	if ($LASTEXITCODE -ne 0) {
		throw "SrxyInstaller.exe compile failed"
	}

	Write-Host "Smoke-testing SrxyInstaller.exe headless engine passthrough..."
	$SmokePrefix = Join-Path $OutDir ("windows-pyside-smoke-" + [guid]::NewGuid().ToString("n"))
	$ack = (& $VenvPy -c "from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION; print(PRIVACY_NOTICE_VERSION)").Trim()
	$env:SRXY_INSTALLER_PAYLOAD = $Payload
	& $VenvPy -m srxy.adapters.inbound.installer --install --prefix $SmokePrefix --privacy-ack $ack --confirm-unsafe --no-add-path
	if ($LASTEXITCODE -ne 0) {
		Remove-Item Env:\SRXY_INSTALLER_PAYLOAD -ErrorAction SilentlyContinue
		throw "payload-driven headless install smoke failed"
	}
	if (-not (Test-Path -LiteralPath (Join-Path $SmokePrefix "bin\Srxy.exe"))) {
		Remove-Item Env:\SRXY_INSTALLER_PAYLOAD -ErrorAction SilentlyContinue
		throw "prebuilt app launcher was not copied from payload during smoke install"
	}
	& $VenvPy -m srxy.adapters.inbound.installer --uninstall --prefix $SmokePrefix --confirm-unsafe | Out-Null
	Remove-Item Env:\SRXY_INSTALLER_PAYLOAD -ErrorAction SilentlyContinue
	Remove-Item -LiteralPath $SmokePrefix -Recurse -Force -ErrorAction SilentlyContinue

	Write-Host "Payload size: $((Get-ChildItem -LiteralPath $Payload -Recurse -Force | Measure-Object -Property Length -Sum).Sum / 1MB) MiB"

	$ZipName = "srxy-$Version-installer-$InstallerVersion-pyside-$Arch.zip"
	$ZipPath = Join-Path $OutDir $ZipName
	if (Test-Path -LiteralPath $ZipPath) {
		Remove-Item -LiteralPath $ZipPath -Force
	}
	Write-Host "Creating $ZipName ..."
	Compress-Archive -Path (Join-Path $Payload "*") -DestinationPath $ZipPath -CompressionLevel Optimal
	$Hash = Get-Sha256Hex -Path $ZipPath
	Set-Content -LiteralPath "$ZipPath.sha256" -Value "$Hash  $ZipName`n" -Encoding ASCII
	$Sums = Join-Path $OutDir "SHA256SUMS-windows-offline-pyside"
	Set-Content -LiteralPath $Sums -Value "$Hash  $ZipName`n" -Encoding ASCII

	Write-Host "Built $ZipPath"
	Write-Host "SHA256 $Hash"
}
finally {
	Pop-Location
}
