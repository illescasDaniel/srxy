#Requires -Version 5.1
<#
.SYNOPSIS
  Build the offline Windows Inno Setup installer (bootstrap Python + bundled wheel).

.DESCRIPTION
  Stages a relocatable CPython with the installer package installed into its
  site-packages (--no-deps, no PySide), a full srxy wheel for prefix installs,
  privacy.txt, then compiles packaging/windows/srxy-offline.iss.

  Prerequisites: uv, Inno Setup 7 (preferred) or 6.2+ with ExecAndLogOutput
  (ISCC.exe on PATH or under Program Files).
#>
param(
	[string]$OutDir = "",
	[string]$PythonVersion = "3.12",
	[string]$IsccPath = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $OutDir) {
	$OutDir = Join-Path $Root "dist"
}

function Find-Iscc {
	param([string]$Explicit)
	if ($Explicit -and (Test-Path -LiteralPath $Explicit)) {
		return (Resolve-Path -LiteralPath $Explicit).Path
	}
	$cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
	if ($cmd) {
		return $cmd.Source
	}
	# Prefer Inno Setup 7 (64-bit Program Files), then 6.
	$candidates = @(
		"${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
		"${env:LocalAppData}\Programs\Inno Setup 7\ISCC.exe",
		"${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
		"${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
		"${env:LocalAppData}\Programs\Inno Setup 6\ISCC.exe",
		"${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
	)
	foreach ($path in $candidates) {
		if ($path -and (Test-Path -LiteralPath $path)) {
			return $path
		}
	}
	throw "ISCC.exe not found. Install Inno Setup 7 (or 6.2+) or pass -IsccPath. See https://jrsoftware.org/isdl.php"
}

function Get-Sha256Hex {
	param([Parameter(Mandatory = $true)][string]$Path)
	# Prefer .NET over Get-FileHash: some hosts (older/constrained PowerShell) lack the cmdlet.
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

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
	throw "uv is required to build the Windows offline installer."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Stage = Join-Path $OutDir "windows-installer-stage"
$Payload = Join-Path $Stage "payload"
$WheelDir = Join-Path $OutDir "windows-installer-wheels"

if (Test-Path -LiteralPath $Stage) {
	Remove-Item -LiteralPath $Stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $Payload "share\srxy") | Out-Null

Push-Location $Root
try {
	$Version = (uv run python -c "from importlib.metadata import version; print(version('srxy'))").Trim()
	$InstallerVersion = (
		uv run python -c "import tomllib,sys; from pathlib import Path; print(tomllib.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))['installer_version'])" `
			(Join-Path $Root "packaging\installer_meta.toml")
	).Trim()

	Write-Host "Building srxy wheel for offline payload..."
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

	$AppPython = Get-ChildItem -LiteralPath $PythonNest -Recurse -Filter "python.exe" |
		Select-Object -First 1
	if (-not $AppPython) {
		throw "managed python.exe not found under $PythonNest"
	}
	$ManagedRoot = $AppPython.Directory.FullName
	Write-Host "Using interpreter: $($AppPython.FullName)"

	# Flatten to payload\python\python.exe (+ DLLs/Lib) so Inno has a stable path.
	$StablePythonDir = Join-Path $Payload "python"
	if (Test-Path -LiteralPath $StablePythonDir) {
		Remove-Item -LiteralPath $StablePythonDir -Recurse -Force
	}
	New-Item -ItemType Directory -Force -Path $StablePythonDir | Out-Null
	Copy-Item -Path (Join-Path $ManagedRoot "*") -Destination $StablePythonDir -Recurse -Force
	Remove-Item -LiteralPath $PythonNest -Recurse -Force
	$BootPy = Join-Path $StablePythonDir "python.exe"
	if (-not (Test-Path -LiteralPath $BootPy)) {
		throw "stable python missing at $BootPy"
	}

	$Site = Join-Path $StablePythonDir "Lib\site-packages"
	New-Item -ItemType Directory -Force -Path $Site | Out-Null
	Write-Host "Installing installer package into bootstrap site-packages (no PySide)..."
	uv pip install --python $BootPy --target $Site --no-deps $Root

	# Relocate probe: copy payload python tree elsewhere and import.
	$RelocProbe = Join-Path $OutDir "windows-reloc-probe"
	if (Test-Path -LiteralPath $RelocProbe) {
		Remove-Item -LiteralPath $RelocProbe -Recurse -Force
	}
	Copy-Item -Path $StablePythonDir -Destination (Join-Path $RelocProbe "python") -Recurse -Force
	$ProbePy = Join-Path $RelocProbe "python\python.exe"
	& $ProbePy -c "from srxy.adapters.inbound.installer.install import InstallOptions; print('bootstrap-ok')"
	if ($LASTEXITCODE -ne 0) {
		throw "relocatable bootstrap import smoke failed"
	}
	Remove-Item -LiteralPath $RelocProbe -Recurse -Force

	Write-Host "Exporting privacy notices (en/es, UTF-8 BOM)..."
	$PrivacyEn = Join-Path $Stage "privacy-en.txt"
	$PrivacyEs = Join-Path $Stage "privacy-es.txt"
	uv run python -c @"
from pathlib import Path
import sys
from srxy.adapters.inbound.installer.privacy import write_privacy_notice_utf8
write_privacy_notice_utf8(Path(sys.argv[1]), language='en')
write_privacy_notice_utf8(Path(sys.argv[2]), language='es')
"@ $PrivacyEn $PrivacyEs
	if ($LASTEXITCODE -ne 0) {
		throw "privacy notice export failed"
	}

	Write-Host "Building Windows GUI launcher + installer icons..."
	$WinShare = Join-Path $Payload "share\srxy\windows"
	New-Item -ItemType Directory -Force -Path $WinShare | Out-Null
	$SetupIco = Join-Path $Stage "srxy-installer.ico"
	$AppIco = Join-Path $WinShare "srxy.ico"
	$LauncherExe = Join-Path $WinShare "Srxy.exe"
	# Use project env (Pillow) — bootstrap is --no-deps and lacks imaging deps.
	uv run python -c @"
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
"@ $SetupIco $AppIco $LauncherExe
	if ($LASTEXITCODE -ne 0) {
		throw "Windows launcher / icon build failed"
	}

	$Iscc = Find-Iscc -Explicit $IsccPath
	$Iss = Join-Path $Root "packaging\windows\srxy-offline.iss"
	# Inno Setup 6.2 treats UTF-8 CustomMessages correctly only with a BOM.
	uv run python -c @"
from pathlib import Path
import sys
path = Path(sys.argv[1])
raw = path.read_bytes()
if not raw.startswith(b'\xef\xbb\xbf'):
    text = raw.decode('utf-8-sig')
    path.write_bytes(b'\xef\xbb\xbf' + text.encode('utf-8'))
    print(f'added UTF-8 BOM to {path}')
else:
    print(f'UTF-8 BOM already present on {path}')
"@ $Iss
	if ($LASTEXITCODE -ne 0) {
		throw "failed to ensure UTF-8 BOM on Inno script"
	}
	$Arch = "x86_64"
	# Compile into a private staging folder first: writing the setup EXE directly
	# under dist\ while Explorer/Defender has a handle often yields
	# EndUpdateResource failed (110) when embedding SetupIconFile.
	$IsccOut = Join-Path $Stage "iscc-out"
	if (Test-Path -LiteralPath $IsccOut) {
		Remove-Item -LiteralPath $IsccOut -Recurse -Force
	}
	New-Item -ItemType Directory -Force -Path $IsccOut | Out-Null
	$PrivacyAckVersion = (uv run python -c "from srxy.adapters.inbound.installer.privacy import PRIVACY_NOTICE_VERSION; print(PRIVACY_NOTICE_VERSION)").Trim()
	if (-not $PrivacyAckVersion) {
		throw "failed to read PRIVACY_NOTICE_VERSION"
	}
	Write-Host "Compiling Inno Setup script with $Iscc (privacy-ack=$PrivacyAckVersion) ..."
	& $Iscc `
		"/DMyAppVersion=$Version" `
		"/DInstallerVersion=$InstallerVersion" `
		"/DArch=$Arch" `
		"/DPayloadDir=$Payload" `
		"/DOutputDir=$IsccOut" `
		"/DPrivacyEnFile=$PrivacyEn" `
		"/DPrivacyEsFile=$PrivacyEs" `
		"/DSetupIconFile=$SetupIco" `
		"/DPrivacyAckVersion=$PrivacyAckVersion" `
		$Iss
	if ($LASTEXITCODE -ne 0) {
		throw "ISCC failed with exit code $LASTEXITCODE"
	}

	$ExeName = "srxy-$Version-installer-$InstallerVersion-$Arch.exe"
	$StagedExe = Join-Path $IsccOut $ExeName
	if (-not (Test-Path -LiteralPath $StagedExe)) {
		throw "expected ISCC output missing: $StagedExe"
	}
	$ExePath = Join-Path $OutDir $ExeName
	Copy-Item -LiteralPath $StagedExe -Destination $ExePath -Force
	$Hash = Get-Sha256Hex -Path $ExePath
	Set-Content -LiteralPath "$ExePath.sha256" -Value "$Hash  $ExeName`n" -Encoding ASCII

	$ZipName = "$ExeName.zip"
	$ZipPath = Join-Path $OutDir $ZipName
	if (Test-Path -LiteralPath $ZipPath) {
		Remove-Item -LiteralPath $ZipPath -Force
	}
	Write-Host "Creating max-compressed zip $ZipName ..."
	uv run python -c @"
import sys
import zipfile
from pathlib import Path
exe = Path(sys.argv[1])
zip_path = Path(sys.argv[2])
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    zf.write(exe, arcname=exe.name)
print(f'wrote {zip_path} ({zip_path.stat().st_size} bytes)')
"@ $ExePath $ZipPath
	if ($LASTEXITCODE -ne 0) {
		throw "installer zip failed"
	}
	$ZipHash = Get-Sha256Hex -Path $ZipPath
	Set-Content -LiteralPath "$ZipPath.sha256" -Value "$ZipHash  $ZipName`n" -Encoding ASCII
	# Published checksum list is zip-only (release / CI artifact).
	$Sums = Join-Path $OutDir "SHA256SUMS-windows-offline"
	Set-Content -LiteralPath $Sums -Value "$ZipHash  $ZipName`n" -Encoding ASCII

	Write-Host "Built $ExePath"
	Write-Host "SHA256 $Hash"
	Write-Host "Zip $ZipPath"
	Write-Host "Zip SHA256 $ZipHash"
}
finally {
	Pop-Location
}
