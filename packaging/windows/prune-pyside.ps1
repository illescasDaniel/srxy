#Requires -Version 5.1
<#
.SYNOPSIS
  Remove unused PySide6 / Qt payload from the Windows offline installer venv.

.DESCRIPTION
  The wizard only needs QGuiApplication + QQml + Qt Quick Controls + FolderDialog.
  Mirrors packaging/macos/prune-pyside.sh and packaging/linux-appimage/prune_pyside.sh,
  adapted for the Windows PySide6 wheel layout: Qt6*.dll sit directly under
  site-packages\PySide6\ (not a nested Qt\lib\), while qml/plugins/translations/
  metatypes live under PySide6\qml\, PySide6\plugins\, etc. (no "Qt\" prefix).

.PARAMETER VenvOrSitePackages
  Either a venv root (containing Scripts\ + Lib\site-packages\PySide6) or a
  site-packages directory (containing PySide6\ directly).
#>
param(
	[Parameter(Mandatory = $true)]
	[string]$VenvOrSitePackages
)

$ErrorActionPreference = "Stop"

function Get-DirSizeHuman {
	param([string]$Path)
	if (-not (Test-Path -LiteralPath $Path)) {
		return "0 B"
	}
	$bytes = (Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
			Measure-Object -Property Length -Sum).Sum
	if (-not $bytes) {
		return "0 B"
	}
	$units = @("B", "KB", "MB", "GB")
	$size = [double]$bytes
	$unitIndex = 0
	while ($size -ge 1024 -and $unitIndex -lt ($units.Length - 1)) {
		$size /= 1024
		$unitIndex += 1
	}
	return "{0:N1} {1}" -f $size, $units[$unitIndex]
}

function Remove-IfExists {
	param([string[]]$Paths)
	foreach ($p in $Paths) {
		if (Test-Path -LiteralPath $p) {
			Remove-Item -LiteralPath $p -Recurse -Force
		}
	}
}

$target = (Resolve-Path -LiteralPath $VenvOrSitePackages).Path
$site = ""
if (Test-Path -LiteralPath (Join-Path $target "PySide6")) {
	$site = $target
}
else {
	$candidate = Join-Path $target "Lib\site-packages"
	if (Test-Path -LiteralPath (Join-Path $candidate "PySide6")) {
		$site = $candidate
	}
}
if (-not $site) {
	throw "no site-packages\PySide6 found under $target"
}

$pside = Join-Path $site "PySide6"
Write-Host "Pruning PySide6 under $pside (before: $(Get-DirSizeHuman $pside))..."

# Dev-time tools/docs not needed at runtime.
Remove-IfExists @(
	Join-Path $pside "assistant.exe"
	Join-Path $pside "designer.exe"
	Join-Path $pside "linguist.exe"
	Join-Path $pside "lupdate.exe"
	Join-Path $pside "lrelease.exe"
	Join-Path $pside "qmlls.exe"
	Join-Path $pside "qmllint.exe"
	Join-Path $pside "qmlformat.exe"
	Join-Path $pside "qsb.exe"
	Join-Path $pside "balsam.exe"
	Join-Path $pside "balsamui.exe"
	Join-Path $pside "doc"
	Join-Path $pside "include"
	Join-Path $pside "typesystems"
	Join-Path $pside "glue"
	Join-Path $pside "metatypes"
	Join-Path $pside "scripts"
	Join-Path $pside "support"
	Join-Path $pside "QtAsyncio"
	Join-Path $pside "py.typed"
	Join-Path $pside "__feature__.pyi"
	Join-Path $pside "_git_pyside_version.py"
)

Get-ChildItem -LiteralPath $pside -Filter "*.pyi" -File -ErrorAction SilentlyContinue |
	ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

# Keep only the bindings the installer imports (or that Quick/QML loads).
$keepBindings = @(
	"QtCore",
	"QtGui",
	"QtQml",
	"QtQuick",
	"QtQuickControls2",
	"QtNetwork",
	"QtOpenGL"
)
Get-ChildItem -LiteralPath $pside -Filter "*.pyd" -File -ErrorAction SilentlyContinue |
	ForEach-Object {
		$base = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
		if ($keepBindings -notcontains $base) {
			Remove-Item -LiteralPath $_.FullName -Force
		}
	}

# Qt6*.dll ship directly under PySide6\ on Windows (no nested Qt\lib\), and newer
# Qt (6.8+) splits modules further than macOS/Linux framework/lib bundles suggest
# (e.g. QtQml itself now needs Qt6QmlCore.dll / Qt6QmlCompiler.dll alongside
# Qt6Qml.dll). An allowlist of "known-needed" DLLs is fragile against that kind of
# split (an incomplete list breaks DLL loading with an opaque "specified module
# could not be found" error rather than a helpful missing-symbol message, and
# this script cannot be iterated against a real Windows PySide6 install). Use a
# DENYLIST of clearly-unused module families instead — everything not matched
# (Core/Gui/Qml*/Quick*/Network/OpenGL/Widgets/Svg/Concurrent/ShaderTools, ANGLE
# (libEGL/libGLESv2/d3dcompiler_47), ICU, and MSVC runtime DLLs) is kept.
$denyDllPatterns = @(
	"Qt63D*.dll",
	"Qt6Bluetooth*.dll",
	"Qt6Charts*.dll",
	"Qt6DataVisualization*.dll",
	"Qt6Designer*.dll",
	"Qt6Graphs*.dll",
	"Qt6Help*.dll",
	"Qt6Location*.dll",
	"Qt6Multimedia*.dll",
	"Qt6NetworkAuth*.dll",
	"Qt6Nfc*.dll",
	"Qt6OpcUa*.dll",
	"Qt6Pdf*.dll",
	"Qt6Positioning*.dll",
	"Qt6PrintSupport*.dll",
	"Qt6Quick3D*.dll",
	"Qt6RemoteObjects*.dll",
	"Qt6Scxml*.dll",
	"Qt6Sensors*.dll",
	"Qt6SerialBus*.dll",
	"Qt6SerialPort*.dll",
	"Qt6Sql*.dll",
	"Qt6StateMachine*.dll",
	"Qt6Test*.dll",
	"Qt6TextToSpeech*.dll",
	"Qt6UiTools*.dll",
	"Qt6VirtualKeyboard*.dll",
	"Qt6WebChannel*.dll",
	"Qt6WebEngine*.dll",
	"Qt6WebSockets*.dll",
	"Qt6WebView*.dll"
)
Get-ChildItem -LiteralPath $pside -Filter "*.dll" -File -ErrorAction SilentlyContinue |
	ForEach-Object {
		$name = $_.Name
		$deny = $false
		foreach ($pattern in $denyDllPatterns) {
			if ($name -like $pattern) {
				$deny = $true
				break
			}
		}
		if ($deny) {
			Remove-Item -LiteralPath $_.FullName -Force
		}
	}

# Unused QML modules (no "Qt\" prefix on Windows; qml\ sits directly under PySide6\).
$qml = Join-Path $pside "qml"
if (Test-Path -LiteralPath $qml) {
	Remove-IfExists @(
		Join-Path $qml "Qt3D"
		Join-Path $qml "Qt5Compat"
		Join-Path $qml "QtCharts"
		Join-Path $qml "QtDataVisualization"
		Join-Path $qml "QtGraphs"
		Join-Path $qml "QtLocation"
		Join-Path $qml "QtMultimedia"
		Join-Path $qml "QtPositioning"
		Join-Path $qml "QtQuick3D"
		Join-Path $qml "QtRemoteObjects"
		Join-Path $qml "QtScxml"
		Join-Path $qml "QtSensors"
		Join-Path $qml "QtTest"
		Join-Path $qml "QtTextToSpeech"
		Join-Path $qml "QtWebChannel"
		Join-Path $qml "QtWebEngine"
		Join-Path $qml "QtWebSockets"
		Join-Path $qml "QtWebView"
		Join-Path $qml "QtWayland"
	)
	$quickQml = Join-Path $qml "QtQuick"
	if (Test-Path -LiteralPath $quickQml) {
		Remove-IfExists @(
			Join-Path $quickQml "Particles"
			Join-Path $quickQml "Pdf"
			Join-Path $quickQml "Scene2D"
			Join-Path $quickQml "Scene3D"
			Join-Path $quickQml "LocalStorage"
			Join-Path $quickQml "Timeline"
			Join-Path $quickQml "VectorImage"
			Join-Path $quickQml "VirtualKeyboard"
			Join-Path $quickQml "tooling"
			(Join-Path $quickQml "Controls\designer")
		)
	}
	$labs = Join-Path $qml "Qt\labs"
	if (Test-Path -LiteralPath $labs) {
		Get-ChildItem -LiteralPath $labs -Directory -ErrorAction SilentlyContinue |
			Where-Object { $_.Name -notin @("folderlistmodel", "qmlmodels") } |
			ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
	}
}

# Unused plugins (also top-level under PySide6\plugins\ on Windows). Kept
# conservative — matches the already-proven macOS/Linux plugin removal lists
# (e.g. "tls" and "networkinformation" are deliberately NOT removed here,
# same as those scripts, since this repo has no Windows host to verify a wider
# list against; the installer uses Python urllib for downloads, not Qt network,
# so this list only trims plugins with no runtime dependency at all).
$plugins = Join-Path $pside "plugins"
if (Test-Path -LiteralPath $plugins) {
	Remove-IfExists @(
		Join-Path $plugins "assetimporters"
		Join-Path $plugins "canbus"
		Join-Path $plugins "designer"
		Join-Path $plugins "gamepads"
		Join-Path $plugins "geometryloaders"
		Join-Path $plugins "geoservices"
		Join-Path $plugins "multimedia"
		Join-Path $plugins "position"
		Join-Path $plugins "printsupport"
		Join-Path $plugins "qmltooling"
		Join-Path $plugins "renderers"
		Join-Path $plugins "renderplugins"
		Join-Path $plugins "sceneparsers"
		Join-Path $plugins "scxmldatamodel"
		Join-Path $plugins "sensors"
		Join-Path $plugins "sqldrivers"
		Join-Path $plugins "texttospeech"
		Join-Path $plugins "video"
		Join-Path $plugins "webview"
	)
}

$afterHuman = Get-DirSizeHuman $pside
Write-Host "Pruned PySide6 to $afterHuman."
