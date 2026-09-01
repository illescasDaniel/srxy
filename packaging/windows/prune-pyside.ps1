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

# Qt6*.dll ship directly under PySide6\ on Windows (no nested Qt\lib\).
$keepDllPatterns = @(
	"Qt6Core.dll", "Qt6Gui.dll", "Qt6Network.dll", "Qt6OpenGL.dll",
	"Qt6Qml.dll", "Qt6QmlMeta.dll", "Qt6QmlModels.dll", "Qt6QmlWorkerScript.dll", "Qt6QmlNetwork.dll",
	"Qt6Quick.dll", "Qt6QuickControls2.dll", "Qt6QuickControls2Impl.dll",
	"Qt6QuickControls2Basic.dll", "Qt6QuickControls2BasicStyleImpl.dll",
	"Qt6QuickControls2Fusion.dll", "Qt6QuickControls2FusionStyleImpl.dll",
	"Qt6QuickControls2Material.dll", "Qt6QuickControls2MaterialStyleImpl.dll",
	"Qt6QuickControls2Imagine.dll", "Qt6QuickControls2ImagineStyleImpl.dll",
	"Qt6QuickControls2Universal.dll", "Qt6QuickControls2UniversalStyleImpl.dll",
	"Qt6QuickControls2FluentWinUI3StyleImpl.dll", "Qt6QuickControls2WindowsStyleImpl.dll",
	"Qt6QuickTemplates2.dll", "Qt6QuickLayouts.dll",
	"Qt6QuickDialogs2.dll", "Qt6QuickDialogs2Utils.dll", "Qt6QuickDialogs2QuickImpl.dll",
	"Qt6QuickEffects.dll", "Qt6QuickShapes.dll",
	"Qt6LabsFolderListModel.dll", "Qt6LabsQmlModels.dll",
	"Qt6ShaderTools.dll", "Qt6Svg.dll", "Qt6Concurrent.dll",
	"pyside6.abi3.dll", "shiboken6.abi3.dll", "MSVCP*.dll", "VCRUNTIME*.dll", "concrt140.dll"
)
Get-ChildItem -LiteralPath $pside -Filter "*.dll" -File -ErrorAction SilentlyContinue |
	ForEach-Object {
		$name = $_.Name
		$keep = $false
		foreach ($pattern in $keepDllPatterns) {
			if ($name -like $pattern) {
				$keep = $true
				break
			}
		}
		if (-not $keep) {
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

# Unused plugins (also top-level under PySide6\plugins\ on Windows).
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
		Join-Path $plugins "networkinformation"
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
		Join-Path $plugins "tls"
		Join-Path $plugins "video"
		Join-Path $plugins "webview"
	)
}

$afterHuman = Get-DirSizeHuman $pside
Write-Host "Pruned PySide6 to $afterHuman."
