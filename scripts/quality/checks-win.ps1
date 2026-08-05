#Requires -Version 5.1
<#
.SYNOPSIS
  Windows-native quality gate (parity with scripts/quality/checks.sh).

.DESCRIPTION
  Ruff, optional ShellCheck/shfmt, basedpyright, pip-audit, wheel build, pytest.
  Use on Windows when bash/flock cannot run ./scripts/quality/checks.sh.

  Flags: -Fix/--fix, -Full/--full, -FullCpu/--full+cpu (same meaning as checks.sh).
  Env: CI=true, LIB_PYTEST_WORKERS (same intent as the bash gate).

  Shell step: WARN-skip when shellcheck/shfmt are missing (common on Windows).
  Light verify steps run sequentially on Windows (bash gate still parallelizes them).
  Stall/wall watchdogs from pytest.sh are not ported; pytest-timeout still applies.

.EXAMPLE
  .\scripts\quality\checks-win.ps1 -Fix
  .\scripts\quality\checks-win.ps1
  $env:CI = 'true'; .\scripts\quality\checks-win.ps1
#>
[CmdletBinding()]
param(
	[switch] $Fix,
	[switch] $Full,
	[switch] $FullCpu,
	# Internal: run one light step and write status (used for parallel verify).
	[string] $InternalStep = '',
	[string] $InternalLog = '',
	[string] $InternalStatus = '',
	[Parameter(ValueFromRemainingArguments = $true)]
	[string[]] $RemainingArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

foreach ($arg in @($RemainingArgs)) {
	switch -Regex ($arg) {
		'^--fix$' { $Fix = $true }
		'^--full$' { $Full = $true }
		'^--full\+cpu$' { $Full = $true; $FullCpu = $true }
	}
}
if ($FullCpu) { $Full = $true }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InternalDir = Join-Path $ScriptDir 'internal'

function Get-RepoRoot {
	param([string] $Start)
	$dir = (Resolve-Path -LiteralPath $Start).Path
	while ($true) {
		if (Test-Path -LiteralPath (Join-Path $dir 'pyproject.toml')) { return $dir }
		$parent = Split-Path -Parent $dir
		if ([string]::IsNullOrEmpty($parent) -or $parent -eq $dir) {
			throw "Could not find project root (pyproject.toml) above $Start"
		}
		$dir = $parent
	}
}

$RepoRoot = Get-RepoRoot -Start $ScriptDir
$LockPath = Join-Path $RepoRoot '.srxy-quality-gate.lock'
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$EmitPy = Join-Path $InternalDir 'gate_emit.py'

$script:GateEmitGha = ($env:GITHUB_ACTIONS -eq 'true')
$script:GateTotalErrors = 0
$script:GateTotalWarnings = 0
$script:GateReport = New-Object 'System.Collections.Generic.List[hashtable]'
$script:GateDetails = New-Object 'System.Collections.Generic.List[string]'
$script:GateCurrentIndex = -1
$script:GatePlannedSteps = 5
$script:LockStream = $null
$script:StatusFile = $null

function Write-GateGhaError {
	param([string] $Title, [string] $Message)
	if (-not $script:GateEmitGha) { return }
	Write-Host "::error title=$Title::$Message"
}

function Start-GateStep {
	param([string] $Name)
	[void]$script:GateReport.Add(@{
		Name     = $Name
		Status   = 'pending'
		Errors   = 0
		Warnings = 0
	})
	$script:GateCurrentIndex = $script:GateReport.Count - 1
	Write-Host ''
	Write-Host ("[{0}/{1}] {2}" -f ($script:GateCurrentIndex + 1), $script:GatePlannedSteps, $Name)
	Write-Host ('-' * 40)
}

function Complete-GateStep {
	param(
		[ValidateSet('pass', 'warn', 'FAIL')]
		[string] $Status,
		[int] $Errors = 0,
		[int] $Warnings = 0,
		[string[]] $Details = @()
	)
	if ($script:StatusFile) {
		$lines = @(
			("status={0}" -f $Status)
			("errors={0}" -f $Errors)
			("warnings={0}" -f $Warnings)
		)
		foreach ($d in $Details) {
			if (-not [string]::IsNullOrWhiteSpace($d)) { $lines += ("detail={0}" -f $d) }
		}
		Set-Content -LiteralPath $script:StatusFile -Value $lines -Encoding ascii
		return
	}
	$row = $script:GateReport[$script:GateCurrentIndex]
	$row['Status'] = $Status
	$row['Errors'] = $Errors
	$row['Warnings'] = $Warnings
	$script:GateTotalErrors += $Errors
	$script:GateTotalWarnings += $Warnings
	foreach ($d in $Details) {
		if (-not [string]::IsNullOrWhiteSpace($d)) { [void]$script:GateDetails.Add($d) }
	}
}

function Invoke-InRepo {
	param([scriptblock] $Block)
	Push-Location -LiteralPath $RepoRoot
	try { & $Block } finally { Pop-Location }
}

function Get-RuffTargets {
	$t = @()
	if (Test-Path (Join-Path $RepoRoot 'src')) { $t += 'src' }
	if (Test-Path (Join-Path $RepoRoot 'tests')) { $t += 'tests' }
	if ($t.Count -eq 0) { $t = @((Join-Path $InternalDir '.')) }
	return $t
}

function Test-Cmd { param([string] $Name) [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Get-PytestWorkers {
	if (-not [string]::IsNullOrWhiteSpace($env:LIB_PYTEST_WORKERS)) { return [int]$env:LIB_PYTEST_WORKERS }
	$n = [Environment]::ProcessorCount
	if ($n -lt 1) { $n = 1 }
	if ($n -gt 4) { $n = 4 }
	return $n
}

function Get-SafeMarker {
	if ($env:CI -eq 'true') {
		return '(unit or gui) and not integration and not semantic and not transcribe'
	}
	return 'unit and not semantic and not transcribe and not gui and not tui and not integration'
}

function Get-HeavyMarker {
	if ($env:LIB_PYTEST_FULL -eq 'true') {
		return 'semantic or transcribe or gui or tui or integration or integration_full or transcribe_device_matrix'
	}
	return '(semantic or transcribe or gui or tui or integration) and not integration_full and not transcribe_device_matrix'
}

function Acquire-GateLock {
	try {
		$script:LockStream = [System.IO.File]::Open(
			$LockPath,
			[System.IO.FileMode]::OpenOrCreate,
			[System.IO.FileAccess]::ReadWrite,
			[System.IO.FileShare]::None
		)
	}
	catch {
		Write-Host "error: another quality gate is already running (lock: $LockPath)." -ForegroundColor Red
		Write-Host 'Stop leftover checks-win.ps1 / checks.sh / pytest processes for this repo, then retry.' -ForegroundColor Red
		exit 1
	}
}

function Release-GateLock {
	if ($null -ne $script:LockStream) {
		$script:LockStream.Close()
		$script:LockStream.Dispose()
		$script:LockStream = $null
	}
}

function Show-GateReport {
	Write-Host ''
	Write-Host ('=' * 39)
	Write-Host ' Quality gate report'
	Write-Host ('=' * 39)
	Write-Host (' {0,-17} {1,-8} {2,7} {3,9}' -f 'Step', 'Status', 'Errors', 'Warnings')
	Write-Host (' ' + ('-' * 45))
	for ($i = 0; $i -lt $script:GateReport.Count; $i++) {
		$row = $script:GateReport[$i]
		$label = switch ($row['Status']) {
			'pass' { 'pass' }
			'warn' { 'WARN' }
			'FAIL' { 'FAIL' }
			default { $row['Status'] }
		}
		Write-Host (' [{0}] {1,-14} {2,-8} {3,7} {4,9}' -f ($i + 1), $row['Name'], $label, $row['Errors'], $row['Warnings'])
	}
	Write-Host (' ' + ('-' * 45))
	Write-Host (' {0,-17} {1,-8} {2,7} {3,9}' -f 'TOTAL', '', $script:GateTotalErrors, $script:GateTotalWarnings)
	Write-Host ''
	if ($script:GateDetails.Count -gt 0) {
		Write-Host 'Details:'
		foreach ($d in $script:GateDetails) { Write-Host ("  {0}" -f $d) }
		Write-Host ''
	}
	if ($script:GateTotalErrors -gt 0) {
		Write-Host ("Result: FAILED ({0} error(s))" -f $script:GateTotalErrors)
	}
	elseif ($script:GateTotalWarnings -gt 0) {
		Write-Host ("Result: PASSED with {0} warning(s)" -f $script:GateTotalWarnings)
	}
	else {
		Write-Host 'Result: PASSED'
	}
}

function Invoke-RuffStep {
	param([bool] $DoFix)
	$targets = Get-RuffTargets
	Invoke-InRepo {
		if ($DoFix) {
			& uv run -- ruff check @targets --fix
			if ($LASTEXITCODE -ne 0) {
				Write-GateGhaError 'ruff' "ruff fix failed (exit $LASTEXITCODE)"
				Complete-GateStep -Status FAIL -Errors 1 -Details @("[ruff] exit $LASTEXITCODE")
				return
			}
			& uv run -- ruff format @targets
			if ($LASTEXITCODE -ne 0) {
				Complete-GateStep -Status FAIL -Errors 1 -Details @("[ruff] format exit $LASTEXITCODE")
				return
			}
			Complete-GateStep -Status pass
			return
		}

		$checkOut = & uv run -- ruff check @targets --output-format=github 2>&1 | ForEach-Object { "$_" }
		$checkOut | Write-Host
		$errors = 0
		$warnings = 0
		if (Test-Path -LiteralPath $EmitPy) {
			$emitOut = $checkOut | & uv run -- python $EmitPy ruff-github 2>&1 | ForEach-Object { "$_" }
			foreach ($line in $emitOut) {
				if ($line -like 'GATE_SUMMARY*') {
					if ($line -match 'errors=(\d+)') { $errors = [int]$Matches[1] }
					if ($line -match 'warnings=(\d+)') { $warnings = [int]$Matches[1] }
				}
				elseif ($line -like '::*') { Write-Host $line }
			}
		}
		elseif ($LASTEXITCODE -ne 0) {
			$errors = 1
		}

		$fmtOut = & uv run -- ruff format --check @targets 2>&1 | ForEach-Object { "$_" }
		$fmtExit = [int]$LASTEXITCODE
		if ($fmtOut) { $fmtOut | Write-Host }
		if ($fmtExit -ne 0) {
			$errors += 1
			Write-GateGhaError 'ruff' 'format check failed'
			Complete-GateStep -Status FAIL -Errors $errors -Warnings $warnings -Details @('[ruff] format check failed')
			return
		}
		if ($errors -gt 0) {
			Complete-GateStep -Status FAIL -Errors $errors -Warnings $warnings
		}
		elseif ($warnings -gt 0) {
			Complete-GateStep -Status warn -Warnings $warnings
		}
		else {
			Complete-GateStep -Status pass
		}
	}
}

function Invoke-ShellStep {
	param([bool] $DoFix)
	if (-not (Test-Cmd 'shellcheck') -or -not (Test-Cmd 'shfmt')) {
		$missing = @()
		if (-not (Test-Cmd 'shellcheck')) { $missing += 'shellcheck' }
		if (-not (Test-Cmd 'shfmt')) { $missing += 'shfmt' }
		Write-Host "note: skipping shell step (missing: $($missing -join ', '))"
		Write-Host 'Install shellcheck + shfmt (scoop/choco) to lint .sh scripts on Windows.'
		Complete-GateStep -Status warn -Warnings 1 -Details @("[shell] skipped; missing $($missing -join ', ')")
		return
	}
	$scripts = @(
		Get-ChildItem -LiteralPath $RepoRoot -Recurse -Filter '*.sh' -File -ErrorAction SilentlyContinue |
			Where-Object {
				$_.FullName -notmatch '[\\/]\.venv[\\/]' -and
				$_.FullName -notmatch '[\\/]node_modules[\\/]' -and
				$_.FullName -notmatch '[\\/]templates[\\/]' -and
				$_.FullName -notmatch '[\\/]dist[\\/]'
			} |
			Sort-Object FullName |
			ForEach-Object { $_.FullName }
	)
	if ($scripts.Count -eq 0) {
		Complete-GateStep -Status pass
		return
	}
	if ($DoFix) {
		& shfmt -i 0 -bn -w @scripts
		if ($LASTEXITCODE -ne 0) {
			Complete-GateStep -Status FAIL -Errors 1 -Details @("[shell] shfmt -w exit $LASTEXITCODE")
			return
		}
	}
	& shfmt -i 0 -bn -d @scripts
	$shfmtExit = [int]$LASTEXITCODE
	& shellcheck -S warning @scripts
	$scExit = [int]$LASTEXITCODE
	if ($shfmtExit -ne 0 -or $scExit -ne 0) {
		Write-GateGhaError 'shell' "shell lint/format failed (shfmt=$shfmtExit shellcheck=$scExit)"
		Complete-GateStep -Status FAIL -Errors 1 -Details @("[shell] shfmt=$shfmtExit shellcheck=$scExit")
		return
	}
	Complete-GateStep -Status pass
}

function Invoke-PyrightStep {
	Invoke-InRepo {
		$stderrFile = [System.IO.Path]::GetTempFileName()
		try {
			$json = & uv run -- basedpyright --outputjson 2>$stderrFile
			$exit = [int]$LASTEXITCODE
			$emitOut = @()
			if (Test-Path -LiteralPath $EmitPy) {
				$emitOut = ($json | & uv run -- python $EmitPy pyright 2>&1 | ForEach-Object { "$_" })
			}
			$summary = $null
			foreach ($line in $emitOut) {
				if ($line -like 'GATE_SUMMARY*') { $summary = $line }
				elseif ($line -like '::*') {
					Write-Host $line
					if ($line -match 'invalid JSON' -and (Get-Item $stderrFile).Length -gt 0) {
						Get-Content -LiteralPath $stderrFile | Write-Host
					}
				}
			}
			if ($summary) {
				$errors = 0; $warnings = 0
				if ($summary -match 'errors=(\d+)') { $errors = [int]$Matches[1] }
				if ($summary -match 'warnings=(\d+)') { $warnings = [int]$Matches[1] }
				if ($errors -gt 0) { Complete-GateStep -Status FAIL -Errors $errors -Warnings $warnings }
				elseif ($warnings -gt 0) { Complete-GateStep -Status warn -Warnings $warnings }
				else { Complete-GateStep -Status pass }
			}
			elseif ($exit -eq 0) { Complete-GateStep -Status pass }
			else {
				Write-GateGhaError 'basedpyright' "type check failed (exit $exit)"
				Complete-GateStep -Status FAIL -Errors 1
			}
		}
		finally {
			Remove-Item -LiteralPath $stderrFile -Force -ErrorAction SilentlyContinue
		}
	}
}

function Invoke-PipAuditStep {
	Invoke-InRepo {
		$pythonBin = (& uv run -- python -c 'import sys; print(sys.executable)').Trim()
		if (-not $pythonBin) {
			Complete-GateStep -Status FAIL -Errors 1 -Details @('[pip-audit] could not resolve python')
			return
		}
		$env:PIPAPI_PYTHON_LOCATION = $pythonBin
		& uv run -- pip-audit --skip-editable
		$code = [int]$LASTEXITCODE
		if ($code -eq 0) { Complete-GateStep -Status pass }
		else {
			Write-GateGhaError 'pip-audit' "dependency audit failed (exit $code)"
			Complete-GateStep -Status FAIL -Errors 1 -Details @("[pip-audit] exit $code")
		}
	}
}

function Invoke-BuildStep {
	$buildDir = Join-Path ([System.IO.Path]::GetTempPath()) ("srxy-build-" + [guid]::NewGuid().ToString('n'))
	New-Item -ItemType Directory -Path $buildDir | Out-Null
	try {
		Invoke-InRepo {
			& uv build --wheel --out-dir $buildDir
			$code = [int]$LASTEXITCODE
			$wheels = @(Get-ChildItem -LiteralPath $buildDir -Filter '*.whl' -File -ErrorAction SilentlyContinue)
			if ($code -ne 0 -or $wheels.Count -eq 0) {
				Write-GateGhaError 'build' "package build failed (exit $code)"
				Complete-GateStep -Status FAIL -Errors 1 -Details @("[build] exit $code")
				return
			}
			Write-Host "Built $($wheels.Count) wheel(s):"
			$wheels | ForEach-Object { Write-Host $_.FullName }
			Complete-GateStep -Status pass
		}
	}
	finally {
		Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
	}
}

function Invoke-PytestOnce {
	param([string[]] $PytestArgs)
	Push-Location -LiteralPath $RepoRoot
	try {
		# Do not let pytest stdout become the function's return value (PowerShell pipeline).
		if (Test-Path -LiteralPath $VenvPython) {
			& $VenvPython -m pytest @PytestArgs 2>&1 | ForEach-Object { Write-Host $_ }
		}
		else {
			& uv run -- pytest @PytestArgs 2>&1 | ForEach-Object { Write-Host $_ }
		}
		return [int]$LASTEXITCODE
	}
	finally {
		Pop-Location
	}
}

function Invoke-PytestStep {
	$workers = Get-PytestWorkers
	$env:PYTHONUNBUFFERED = '1'
	$env:LIB_PYTEST_WORKERS = "$workers"

	$safe = @('tests', '-m', (Get-SafeMarker), '-n', "$workers", '--dist=loadgroup', '--max-worker-restart=0')
	if ($env:CI -ne 'true' -and $env:LIB_PYTEST_FULL -ne 'true') {
		$safe += @('--testmon-forceselect', '--ff')
	}
	if ($env:LIB_PYTEST_FULL -eq 'true' -and (Test-Path (Join-Path $RepoRoot 'src'))) {
		$safe += @('--cov=src', '--cov-report=term-missing:skip-covered', '-ra', '--tb=short')
	}

	Write-Host "pytest: safe parallel pass (workers=$workers)"
	Write-Host ("pytest: args: " + ($safe -join ' '))
	$code = Invoke-PytestOnce -PytestArgs $safe
	if ($code -ne 0) {
		Write-GateGhaError 'pytest' "tests failed (exit $code)"
		Complete-GateStep -Status FAIL -Errors 1 -Details @("[pytest] exit $code")
		return
	}

	if ($env:CI -eq 'true') {
		Complete-GateStep -Status pass
		return
	}

	$heavy = @('tests', '-m', (Get-HeavyMarker), '-n', '0')
	if ($env:LIB_PYTEST_FULL_CPU -eq 'true') { $heavy += '--integration-test-cpu' }
	if ($env:LIB_PYTEST_FULL -eq 'true' -and (Test-Path (Join-Path $RepoRoot 'src'))) {
		$heavy += @('--cov=src', '--cov-append', '--cov-report=term-missing:skip-covered', '-ra', '--tb=short')
	}

	Write-Host ''
	Write-Host 'Serial heavy pass (semantic/transcribe/gui/tui/integration, QT_QPA_PLATFORM=offscreen, -n 0)'
	$prevQt = $env:QT_QPA_PLATFORM
	$env:QT_QPA_PLATFORM = 'offscreen'
	try {
		$code = Invoke-PytestOnce -PytestArgs $heavy
	}
	finally {
		if ($null -eq $prevQt) { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
		else { $env:QT_QPA_PLATFORM = $prevQt }
	}
	if ($code -ne 0) {
		Write-GateGhaError 'pytest' "tests failed (exit $code)"
		Complete-GateStep -Status FAIL -Errors 1 -Details @("[pytest] heavy exit $code")
		return
	}
	Complete-GateStep -Status pass
}

function Invoke-NamedStep {
	param([string] $Name, [bool] $DoFix)
	switch ($Name) {
		'ruff' { Invoke-RuffStep -DoFix $DoFix }
		'shell' { Invoke-ShellStep -DoFix $DoFix }
		'basedpyright' { Invoke-PyrightStep }
		'pip-audit' { Invoke-PipAuditStep }
		'build' { Invoke-BuildStep }
		'pytest' { Invoke-PytestStep }
		default { throw "unknown step: $Name" }
	}
}

# --- internal one-step mode (parallel parent) ---
if (-not [string]::IsNullOrWhiteSpace($InternalStep)) {
	$script:StatusFile = $InternalStatus
	try {
		Invoke-NamedStep -Name $InternalStep -DoFix:$false
		if (-not (Test-Path -LiteralPath $InternalStatus)) {
			Complete-GateStep -Status FAIL -Errors 1 -Details @("[gate] step $InternalStep wrote no status")
		}
		exit 0
	}
	catch {
		Complete-GateStep -Status FAIL -Errors 1 -Details @("[gate] $($_.Exception.Message)")
		exit 1
	}
}

# --- main gate ---
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.venv'))) {
	Write-Host 'Missing .venv. Create it first: uv sync --extra semantic --extra windows' -ForegroundColor Red
	exit 1
}

if ($env:GITHUB_ACTIONS -eq 'true' -and $Fix) {
	Write-Host 'note: -Fix ignored in GitHub Actions (check-only mode)'
	$Fix = $false
}
if ($env:GITHUB_ACTIONS -eq 'true' -and ($Full -or $FullCpu)) {
	Write-Host 'note: -Full/-FullCpu ignored in GitHub Actions'
	$Full = $false
	$FullCpu = $false
}
# Local CI=true mimics day-to-day/CI pytest markers, but explicit -Full must still run heavy tests.
if ($env:CI -eq 'true' -and $env:GITHUB_ACTIONS -ne 'true' -and ($Full -or $FullCpu)) {
	Write-Host 'note: clearing CI=true for explicit -Full/-FullCpu (local gate)'
	Remove-Item Env:CI -ErrorAction SilentlyContinue
}

$env:LIB_PYTEST_FULL = $(if ($Full) { 'true' } else { 'false' })
$env:LIB_PYTEST_FULL_CPU = $(if ($FullCpu) { 'true' } else { 'false' })
if ([string]::IsNullOrWhiteSpace($env:LIB_PYTEST_WORKERS)) {
	$env:LIB_PYTEST_WORKERS = "$(Get-PytestWorkers)"
}

$hasPytest = Test-Path -LiteralPath (Join-Path $RepoRoot 'tests')
if ($hasPytest) { $script:GatePlannedSteps = 6 }

Acquire-GateLock
try {
	Set-Location -LiteralPath $RepoRoot

	if ($Fix) {
		foreach ($name in @('ruff', 'shell', 'basedpyright', 'pip-audit', 'build')) {
			Start-GateStep $name
			Invoke-NamedStep -Name $name -DoFix:$true
		}
		if ($hasPytest) {
			Start-GateStep 'pytest'
			Invoke-PytestStep
		}
	}
	else {
		Write-Host ("Verify (sequential light steps; then pytest -n {0}, heavy serial)" -f $env:LIB_PYTEST_WORKERS)
		foreach ($name in @('ruff', 'shell', 'basedpyright', 'pip-audit', 'build')) {
			Start-GateStep $name
			Invoke-NamedStep -Name $name -DoFix:$false
		}
		if ($hasPytest) {
			Start-GateStep 'pytest'
			Invoke-PytestStep
		}
	}

	Show-GateReport
	if ($script:GateTotalErrors -gt 0) { exit 1 }
	exit 0
}
finally {
	Release-GateLock
}
