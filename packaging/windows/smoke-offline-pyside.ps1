#Requires -Version 5.1
<#
.SYNOPSIS
  Smoke-test the built Windows PySide offline installer payload.

.DESCRIPTION
  Without -Payload: locates dist\windows-pyside-installer-stage\payload from a
  prior build-offline-pyside.ps1 run. Relocates a copy to a temp directory
  first (same relocation-bug class as packaging/macos/smoke-offline.sh /
  packaging/linux-appimage/smoke-appimage.sh), then:
    - runs the wizard-only venv's pruned QtQuick.Controls QML smoke,
    - drives a full headless install + uninstall through SrxyInstaller.exe's
      underlying venv with SRXY_INSTALLER_PAYLOAD set, verifying the bundled
      wheel / prebuilt app launcher resolve from the payload (not PyPI).

.PARAMETER Payload
  Path to a built payload directory (defaults to the latest local build).
#>
param(
	[string]$Payload = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $Payload) {
	$Payload = Join-Path $Root "dist\windows-pyside-installer-stage\payload"
}
if (-not (Test-Path -LiteralPath $Payload)) {
	throw "payload not found: $Payload (run build-offline-pyside.ps1 first, or pass -Payload)"
}
$BuiltPayload = (Resolve-Path -LiteralPath $Payload).Path

# Relocate before smoke-testing: a payload with an absolute build-host symlink
# or path baked into pyvenv.cfg would still work in place but break once the
# zip is extracted on a user's machine.
$StageDir = Join-Path $env:TEMP ("srxy-pyside-smoke-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
$SmokePayload = Join-Path $StageDir "payload"
Copy-Item -Path $BuiltPayload -Destination $SmokePayload -Recurse -Force
Write-Host "Smoke-testing relocated copy: $SmokePayload (built at $BuiltPayload)"

try {
	$VenvPy = Join-Path $SmokePayload "venv\Scripts\python.exe"
	$LauncherExe = Join-Path $SmokePayload "SrxyInstaller.exe"
	if (-not (Test-Path -LiteralPath $VenvPy)) {
		throw "wizard python not found: $VenvPy"
	}
	if (-not (Test-Path -LiteralPath $LauncherExe)) {
		throw "SrxyInstaller.exe not found: $LauncherExe"
	}

	Write-Host "Wizard import + QML smoke (offscreen)..."
	$env:QT_QPA_PLATFORM = "offscreen"
	& $VenvPy -c "import srxy.adapters.inbound.installer"
	if ($LASTEXITCODE -ne 0) {
		throw "relocated wizard import smoke failed"
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
	raise SystemExit("relocated QML smoke failed: no root objects")
print("relocated QML smoke OK")
"@
	& $VenvPy -c $QmlSmoke
	if ($LASTEXITCODE -ne 0) {
		throw "relocated QML smoke failed"
	}
	Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue

	Write-Host "Headless install/uninstall through the relocated payload..."
	$Prefix = Join-Path $StageDir "prefix"
	$env:SRXY_INSTALLER_PAYLOAD = $SmokePayload
	try {
		$ack = (& $VenvPy -c "from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION; print(PRIVACY_NOTICE_VERSION)").Trim()
		& $VenvPy -m srxy.adapters.inbound.installer --install --prefix $Prefix --privacy-ack $ack --confirm-unsafe --no-add-path
		if ($LASTEXITCODE -ne 0) {
			throw "headless install failed"
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
		& $VenvPy -m srxy.adapters.inbound.installer --uninstall --prefix $Prefix --confirm-unsafe
		if ($LASTEXITCODE -ne 0) {
			throw "headless uninstall failed"
		}
		if (Test-Path -LiteralPath $Prefix) {
			throw "prefix still exists after uninstall: $Prefix"
		}
	}
	finally {
		Remove-Item Env:\SRXY_INSTALLER_PAYLOAD -ErrorAction SilentlyContinue
	}

	Write-Host "PySide offline wrapper smoke OK: $SmokePayload"
}
finally {
	Remove-Item -LiteralPath $StageDir -Recurse -Force -ErrorAction SilentlyContinue
}
