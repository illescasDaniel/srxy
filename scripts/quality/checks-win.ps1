#Requires -Version 5.1
<#
.SYNOPSIS
  Windows-native quality gate (parity with scripts/quality/checks.sh).

.DESCRIPTION
  Ruff, optional ShellCheck/shfmt, basedpyright, pip-audit, wheel build, pytest buckets.
  Use on Windows when bash/flock cannot run ./scripts/quality/checks.sh.

  Flags: -Fix/--fix, -Full/--full, -FullCpu/--full+cpu, -Quiet/--quiet,
  -Timings/--timings, -NoCache/--no-cache, -Scope, -All/--all, -Core/--core,
  -Cli/--cli, -Tui/--tui, -Gui/--gui (same intent as checks.sh).

  Env: CI=true, LIB_PYTEST_WORKERS, LIB_GATE_SCOPE, LIB_GATE_QUIET, LIB_GATE_TIMINGS,
  LIB_GATE_NO_CACHE, LIB_GATE_BUCKET_CONCURRENCY, LIB_PYTEST_WALL_SECONDS.

  Shell step: WARN-skip when shellcheck/shfmt are missing (common on Windows).
  Verify path: parallel light steps (Start-Process) overlapping pytest buckets.
  Pytest: core/gui/tui/heavy buckets (longest-job-first), wall watchdog, per-bucket testmon.
  Step cache under .gate-cache/ for pip-audit (uv.lock) and build (pyproject.toml).

.EXAMPLE
  .\scripts\quality\checks-win.ps1 -Fix
  .\scripts\quality\checks-win.ps1 -Quiet
  .\scripts\quality\checks-win.ps1 -Scope core,gui
  $env:CI = 'true'; .\scripts\quality\checks-win.ps1
#>
[CmdletBinding()]
param(
	[switch] $Fix,
	[switch] $Full,
	[switch] $FullCpu,
	[switch] $Quiet,
	[switch] $Timings,
	[switch] $NoCache,
	[string] $Scope = 'auto',
	[switch] $All,
	[switch] $Core,
	[switch] $Cli,
	[switch] $Tui,
	[switch] $Gui,
	# Internal: run one light step and write status (used for parallel verify).
	[string] $InternalStep = '',
	[string] $InternalLog = '',
	[string] $InternalStatus = '',
	# Internal: run one pytest bucket and write status.
	[string] $InternalBucket = '',
	[Parameter(ValueFromRemainingArguments = $true)]
	[string[]] $RemainingArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$script:ScopeSet = $false

foreach ($arg in @($RemainingArgs)) {
	switch -Regex ($arg) {
		'^--fix$' { $Fix = $true }
		'^--full$' { $Full = $true }
		'^--full\+cpu$' { $Full = $true; $FullCpu = $true }
		'^--quiet$' { $Quiet = $true }
		'^--timings$' { $Timings = $true }
		'^--no-cache$' { $NoCache = $true }
		'^--all$' { $Scope = 'all'; $script:ScopeSet = $true }
		'^--core$' {
			if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,core" }
			else { $Scope = 'core'; $script:ScopeSet = $true }
		}
		'^--cli$' {
			if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,cli" }
			else { $Scope = 'cli'; $script:ScopeSet = $true }
		}
		'^--tui$' {
			if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,tui" }
			else { $Scope = 'tui'; $script:ScopeSet = $true }
		}
		'^--gui$' {
			if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,gui" }
			else { $Scope = 'gui'; $script:ScopeSet = $true }
		}
		'^--scope=(.+)$' { $Scope = $Matches[1]; $script:ScopeSet = $true }
	}
}

if ($All) { $Scope = 'all'; $script:ScopeSet = $true }
if ($Core) {
	if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,core" }
	else { $Scope = 'core'; $script:ScopeSet = $true }
}
if ($Cli) {
	if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,cli" }
	else { $Scope = 'cli'; $script:ScopeSet = $true }
}
if ($Tui) {
	if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,tui" }
	else { $Scope = 'tui'; $script:ScopeSet = $true }
}
if ($Gui) {
	if ($script:ScopeSet -and $Scope -ne 'auto') { $Scope = "$Scope,gui" }
	else { $Scope = 'gui'; $script:ScopeSet = $true }
}
# -Scope param counts as explicit when not default auto
if ($PSBoundParameters.ContainsKey('Scope') -and $Scope -ne 'auto') {
	$script:ScopeSet = $true
}

if ($FullCpu) { $Full = $true }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InternalDir = Join-Path $ScriptDir 'internal'
$PSCommandPathResolved = $MyInvocation.MyCommand.Path

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
$VenvDir = Join-Path $RepoRoot '.venv\Scripts'
$VenvPython = Join-Path $VenvDir 'python.exe'
$EmitPy = Join-Path $InternalDir 'gate_emit.py'
$GateCacheDir = Join-Path $RepoRoot '.gate-cache'

$script:BucketOrder = @('heavy', 'gui', 'tui', 'core')
$script:SelectedBuckets = @()
$script:ScopeReason = ''
$script:LastPytestExit = 0
$script:GateEmitGha = ($env:GITHUB_ACTIONS -eq 'true')
$script:GateTotalErrors = 0
$script:GateTotalWarnings = 0
$script:GateReport = New-Object 'System.Collections.Generic.List[hashtable]'
$script:GateDetails = New-Object 'System.Collections.Generic.List[string]'
$script:GateCurrentIndex = -1
$script:GatePlannedSteps = 5
$script:GateStepStart = $null
$script:LockStream = $null
$script:StatusFile = $null
$script:GateLogFile = $null

function Write-GateHost {
	param(
		[Parameter(Position = 0, ValueFromRemainingArguments = $true)]
		[object[]] $Object,
		[ConsoleColor] $ForegroundColor
	)
	$msg = ($Object | ForEach-Object { "$_" }) -join ' '
	if ($script:GateLogFile) {
		Add-Content -LiteralPath $script:GateLogFile -Value $msg -Encoding UTF8
		return
	}
	if ($PSBoundParameters.ContainsKey('ForegroundColor')) {
		Write-Host $msg -ForegroundColor $ForegroundColor
	}
	else {
		Write-Host $msg
	}
}

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
		Seconds  = 0
	})
	$script:GateCurrentIndex = $script:GateReport.Count - 1
	$script:GateStepStart = Get-Date
	Write-Host ''
	Write-Host ("[{0}/{1}] {2}" -f ($script:GateCurrentIndex + 1), $script:GatePlannedSteps, $Name)
	Write-Host ('-' * 40)
}

function Complete-GateStep {
	param(
		[ValidateSet('pass', 'warn', 'FAIL', 'skip')]
		[string] $Status,
		[int] $Errors = 0,
		[int] $Warnings = 0,
		[string[]] $Details = @(),
		[int] $Seconds = -1
	)
	$elapsed = $Seconds
	if ($elapsed -lt 0) {
		if ($null -ne $script:GateStepStart) {
			$elapsed = [int][Math]::Max(0, ((Get-Date) - $script:GateStepStart).TotalSeconds)
		}
		else {
			$elapsed = 0
		}
	}
	if ($script:StatusFile) {
		$lines = @(
			("status={0}" -f $Status)
			("errors={0}" -f $Errors)
			("warnings={0}" -f $Warnings)
			("seconds={0}" -f $elapsed)
		)
		foreach ($d in $Details) {
			if (-not [string]::IsNullOrWhiteSpace($d)) { $lines += ("detail={0}" -f $d) }
		}
		Set-Content -LiteralPath $script:StatusFile -Value $lines -Encoding ascii
		return
	}
	# Write through the list indexer — copying the hashtable into a local
	# variable has been flaky under StrictMode + Generic.List on Windows PS 5.1.
	$script:GateReport[$script:GateCurrentIndex]['Status'] = $Status
	$script:GateReport[$script:GateCurrentIndex]['Errors'] = $Errors
	$script:GateReport[$script:GateCurrentIndex]['Warnings'] = $Warnings
	$script:GateReport[$script:GateCurrentIndex]['Seconds'] = $elapsed
	$script:GateTotalErrors += $Errors
	$script:GateTotalWarnings += $Warnings
	foreach ($d in $Details) {
		if (-not [string]::IsNullOrWhiteSpace($d)) { [void]$script:GateDetails.Add($d) }
	}
}

function Import-GateStatusFile {
	param(
		[string] $File,
		[int] $FallbackSeconds = 0
	)
	$status = 'FAIL'
	$errors = 1
	$warnings = 0
	$seconds = $FallbackSeconds
	$details = @()
	if (-not (Test-Path -LiteralPath $File)) {
		Complete-GateStep -Status FAIL -Errors 1 -Details @("[gate] missing status file: $File") -Seconds $FallbackSeconds
		return
	}
	Get-Content -LiteralPath $File -ErrorAction SilentlyContinue | ForEach-Object {
		$line = $_
		if ($line -match '^status=(.+)$') { $status = $Matches[1] }
		elseif ($line -match '^errors=(\d+)$') { $errors = [int]$Matches[1] }
		elseif ($line -match '^warnings=(\d+)$') { $warnings = [int]$Matches[1] }
		elseif ($line -match '^seconds=(\d+)$') { $seconds = [int]$Matches[1] }
		elseif ($line -match '^detail=(.*)$') { $details += $Matches[1] }
	}
	if ($status -notin @('pass', 'warn', 'FAIL', 'skip')) { $status = 'FAIL' }
	Complete-GateStep -Status $status -Errors $errors -Warnings $warnings -Details $details -Seconds $seconds
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

function Get-VenvExe {
	param([string] $Name)
	$p = Join-Path $VenvDir ($Name + '.exe')
	if (Test-Path -LiteralPath $p) { return $p }
	return $null
}

function Invoke-VenvOrUv {
	param(
		[Parameter(Mandatory = $true)]
		[string] $Name,
		[string[]] $ToolArgs = @()
	)
	# Never return stdout via the success stream — callers assign the exit
	# code from $script:LastToolExit so tool output cannot pollute it.
	$script:LastToolExit = 1
	$exe = Get-VenvExe -Name $Name
	if ($exe) {
		& $exe @ToolArgs
		$script:LastToolExit = [int]$LASTEXITCODE
		return
	}
	$prev = $env:UV_NO_SYNC
	$env:UV_NO_SYNC = '1'
	try {
		& uv run -- $Name @ToolArgs
		$script:LastToolExit = [int]$LASTEXITCODE
	}
	finally {
		if ($null -eq $prev) { Remove-Item Env:UV_NO_SYNC -ErrorAction SilentlyContinue }
		else { $env:UV_NO_SYNC = $prev }
	}
}

function Invoke-GatePython {
	param([string[]] $PythonArgs)
	$script:LastToolExit = 1
	if (Test-Path -LiteralPath $VenvPython) {
		& $VenvPython @PythonArgs
		$script:LastToolExit = [int]$LASTEXITCODE
		return
	}
	$prev = $env:UV_NO_SYNC
	$env:UV_NO_SYNC = '1'
	try {
		& uv run -- python @PythonArgs
		$script:LastToolExit = [int]$LASTEXITCODE
	}
	finally {
		if ($null -eq $prev) { Remove-Item Env:UV_NO_SYNC -ErrorAction SilentlyContinue }
		else { $env:UV_NO_SYNC = $prev }
	}
}

function Get-FileSha256 {
	param([string] $Path)
	if (-not (Test-Path -LiteralPath $Path)) { return '' }
	return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-GateCacheHit {
	param(
		[string] $Name,
		[string] $Hash,
		[int] $MaxAgeDays = 7
	)
	if ($env:LIB_GATE_NO_CACHE -eq 'true') { return $false }
	if ($env:LIB_PYTEST_FULL -eq 'true') { return $false }
	if ($env:CI -eq 'true') { return $false }
	if ([string]::IsNullOrWhiteSpace($Hash)) { return $false }
	$marker = Join-Path $GateCacheDir ($Name + '.ok')
	if (-not (Test-Path -LiteralPath $marker)) { return $false }
	$stored = (Get-Content -LiteralPath $marker -Raw -ErrorAction SilentlyContinue).Trim()
	if ($stored -ne $Hash) { return $false }
	$age = (Get-Date) - (Get-Item -LiteralPath $marker).LastWriteTime
	if ($age.TotalDays -gt $MaxAgeDays) { return $false }
	return $true
}

function Save-GateCache {
	param([string] $Name, [string] $Hash)
	if ([string]::IsNullOrWhiteSpace($Hash)) { return }
	if (-not (Test-Path -LiteralPath $GateCacheDir)) {
		New-Item -ItemType Directory -Path $GateCacheDir -Force | Out-Null
	}
	Set-Content -LiteralPath (Join-Path $GateCacheDir ($Name + '.ok')) -Value $Hash -Encoding ascii
}

function Get-Nproc {
	$n = [Environment]::ProcessorCount
	if ($n -lt 1) { $n = 1 }
	return $n
}

function Get-PytestWorkers {
	if (-not [string]::IsNullOrWhiteSpace($env:LIB_PYTEST_WORKERS)) {
		return [int]$env:LIB_PYTEST_WORKERS
	}
	$n = Get-Nproc
	$reserved = 1
	if (-not [string]::IsNullOrWhiteSpace($env:LIB_GATE_ACTIVE_BUCKETS)) {
		$reserved = [int]$env:LIB_GATE_ACTIVE_BUCKETS
		if ($reserved -lt 1) { $reserved = 1 }
	}
	$cap = $n - $reserved + 1
	if ($cap -lt 2) { $cap = 2 }
	if ($cap -gt 8) { $cap = 8 }
	if ($n -lt $cap) { $cap = $n }
	if ($cap -lt 1) { $cap = 1 }
	return $cap
}

function Get-PytestWallSeconds {
	if (-not [string]::IsNullOrWhiteSpace($env:LIB_PYTEST_WALL_SECONDS)) {
		return [int]$env:LIB_PYTEST_WALL_SECONDS
	}
	if ($env:CI -eq 'true') { return 300 }
	if ($env:LIB_PYTEST_FULL -eq 'true') { return 1800 }
	return 600
}

function Get-ShellScripts {
	$found = New-Object 'System.Collections.Generic.List[string]'
	foreach ($rel in @('scripts', 'packaging')) {
		$dir = Join-Path $RepoRoot $rel
		if (Test-Path -LiteralPath $dir) {
			Get-ChildItem -LiteralPath $dir -Recurse -Filter '*.sh' -File -ErrorAction SilentlyContinue |
				ForEach-Object { [void]$found.Add($_.FullName) }
		}
	}
	Get-ChildItem -LiteralPath $RepoRoot -Filter '*.sh' -File -ErrorAction SilentlyContinue |
		ForEach-Object { [void]$found.Add($_.FullName) }
	return @($found | Sort-Object -Unique)
}

function Resolve-GateBuckets {
	$scope = $env:LIB_GATE_SCOPE
	if ([string]::IsNullOrWhiteSpace($scope)) { $scope = 'auto' }
	$scope = $scope.Trim().ToLowerInvariant()

	switch ($scope) {
		{ $_ -in @('all', 'full') } {
			$selected = @($script:BucketOrder)
			if ($env:CI -eq 'true' -and $env:LIB_PYTEST_FULL -ne 'true' -and $scope -ne 'all') {
				$selected = @('gui', 'tui', 'core')
				$script:ScopeReason = 'CI default (core+gui+tui)'
			}
			else {
				$script:ScopeReason = 'explicit all'
			}
			$script:SelectedBuckets = @($selected)
			return
		}
		'auto' {
			Resolve-AutoScopeBuckets
			return
		}
		default {
			$raw = @($scope -split ',' | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ })
			$reason = "explicit --scope=$scope"
			$normalized = @()
			foreach ($bucket in $script:BucketOrder) {
				foreach ($s in $raw) {
					$item = $s
					if ($item -eq 'cli') { $item = 'core' }
					if ($item -eq $bucket) {
						$normalized += $bucket
						break
					}
				}
			}
			if ($normalized.Count -eq 0) {
				$normalized = @('core')
				$reason = "$reason; fell back to core (empty selection)"
			}
			$script:SelectedBuckets = @($normalized)
			$script:ScopeReason = $reason
		}
	}
}

function Resolve-AutoScopeBuckets {
	$want = @{ core = $true }
	$ambiguous = $false
	$paths = New-Object 'System.Collections.Generic.List[string]'

	$gitOk = $false
	if (Test-Cmd 'git') {
		Push-Location -LiteralPath $RepoRoot
		try {
			$inside = & git rev-parse --is-inside-work-tree 2>$null
			if ($LASTEXITCODE -eq 0 -and "$inside".Trim() -eq 'true') { $gitOk = $true }
		}
		finally { Pop-Location }
	}
	if (-not $gitOk) {
		$script:SelectedBuckets = @($script:BucketOrder)
		$script:ScopeReason = 'auto -> all (no git)'
		return
	}

	Push-Location -LiteralPath $RepoRoot
	try {
		$mergeBase = & git merge-base HEAD origin/main 2>$null
		if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($mergeBase)) {
			$mergeBase = & git merge-base HEAD main 2>$null
		}
		if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($mergeBase)) {
			& git diff --name-only "$($mergeBase.Trim())...HEAD" 2>$null | ForEach-Object {
				if ($_ ) { [void]$paths.Add($_) }
			}
		}
		& git status --porcelain 2>$null | ForEach-Object {
			$line = $_
			if ([string]::IsNullOrWhiteSpace($line) -or $line.Length -lt 4) { return }
			$path = $line.Substring(3)
			if ($path -match ' -> ') { $path = ($path -split ' -> ', 2)[0] }
			$path = $path.Trim().Trim('"')
			if ($path) { [void]$paths.Add($path) }
		}
	}
	finally { Pop-Location }

	if ($paths.Count -eq 0) {
		$script:SelectedBuckets = @('core')
		$script:ScopeReason = 'auto -> core (clean tree)'
		return
	}

	foreach ($path in $paths) {
		$p = ($path -replace '\\', '/').Trim()
		# Mirror bash case order: specific prefixes first, ambiguous next, then broad core.
		if ($p -like 'src/srxy/adapters/inbound/gui/*' -or
			$p -like 'src/srxy/adapters/inbound/shared/qml/*' -or
			$p -like 'src/srxy/adapters/inbound/installer/*' -or
			$p -like 'tests/gui/*') {
			$want['gui'] = $true
		}
		elseif ($p -like 'src/srxy/adapters/inbound/tui/*' -or $p -like 'tests/tui/*') {
			$want['tui'] = $true
		}
		elseif ($p -like 'src/srxy/adapters/inbound/cli/*' -or $p -like 'tests/cli/*') {
			$want['core'] = $true
		}
		elseif ($p -like 'src/srxy/adapters/outbound/semantic/*' -or
			$p -like 'src/srxy/adapters/outbound/transcribe/*' -or
			$p -like 'src/srxy/adapters/outbound/ocr/*' -or
			$p -like 'src/srxy/adapters/outbound/models/*' -or
			$p -eq 'src/srxy/application/matching/semantic.py' -or
			$p -like 'tests/fixtures/*' -or
			$p -like 'tests/integration/*') {
			$want['heavy'] = $true
		}
		elseif ($p -eq 'pyproject.toml' -or
			$p -eq 'tests/conftest.py' -or
			$p -eq 'tests/helpers.py' -or
			$p -eq 'tests/isolation.py' -or
			$p -like 'scripts/quality/*' -or
			$p -like '.github/*') {
			$ambiguous = $true
		}
		elseif ($p -like 'src/srxy/*' -or
			$p -like 'tests/unit/*' -or
			$p -like 'packaging/*' -or
			$p -like 'scripts/*' -or
			$p -like 'assets/*') {
			$want['core'] = $true
		}
		else {
			$ambiguous = $true
		}
	}

	if ($ambiguous) {
		$script:SelectedBuckets = @($script:BucketOrder)
		$script:ScopeReason = 'auto -> all (ambiguous paths)'
		return
	}

	if ($env:CI -eq 'true' -and $env:LIB_PYTEST_FULL -ne 'true') {
		$want.Remove('heavy')
	}

	$selected = @()
	foreach ($bucket in $script:BucketOrder) {
		if ($want.ContainsKey($bucket) -and $want[$bucket]) {
			$selected += $bucket
		}
	}
	$script:SelectedBuckets = @($selected)
	$script:ScopeReason = "auto -> $($script:SelectedBuckets -join ' ')"
}

function Get-BucketPytestArgs {
	param([string] $Bucket)
	# Returns hashtable: Paths/Args present, EnvPairs list, TestmonFile, Empty
	$result = @{
		Args        = @()
		EnvPairs    = @()
		TestmonFile = ''
		Empty       = $true
	}

	$paths = @()
	$workers = 0
	$enableQt = $false

	switch ($Bucket) {
		'core' {
			$paths = @('tests/unit', 'tests/cli')
			$workers = Get-PytestWorkers
			$result.TestmonFile = '.testmondata-core'
		}
		'gui' {
			$paths = @('tests/gui')
			$workers = 0
			$enableQt = $true
			$result.EnvPairs += 'QT_QPA_PLATFORM=offscreen'
			$result.TestmonFile = '.testmondata-gui'
		}
		'tui' {
			$paths = @('tests/tui')
			$workers = 0
			$result.TestmonFile = '.testmondata-tui'
		}
		'heavy' {
			$paths = @('tests/integration')
			$workers = 0
			$result.EnvPairs += @(
				'QT_QPA_PLATFORM=offscreen'
				'OMP_NUM_THREADS=1'
				'MKL_NUM_THREADS=1'
				'TOKENIZERS_PARALLELISM=false'
			)
			if ($env:LIB_PYTEST_FULL -ne 'true') {
				$result.EnvPairs += @('HF_HUB_OFFLINE=1', 'TRANSFORMERS_OFFLINE=1')
			}
			$result.TestmonFile = '.testmondata-heavy'
		}
		default {
			throw "unknown bucket: $Bucket"
		}
	}

	$args = @()
	foreach ($p in $paths) {
		if (Test-Path -LiteralPath (Join-Path $RepoRoot $p)) {
			$args += $p
		}
	}
	if ($args.Count -eq 0) {
		return $result
	}
	$result.Empty = $false

	switch ($Bucket) {
		'core' {
			# Paths already isolate Qt/Textual/real backends; no -m filter.
		}
		'heavy' {
			if ($env:LIB_PYTEST_FULL -ne 'true') {
				$args += @('-m', 'not integration_full and not transcribe_device_matrix')
			}
			if ($env:LIB_PYTEST_FULL_CPU -eq 'true') {
				$args += '--integration-test-cpu'
			}
		}
	}

	if ($workers -gt 0) {
		$args += @('-n', "$workers", '--dist=loadgroup', '--max-worker-restart=0')
	}
	# Serial buckets omit -n; keep xdist loaded so agent_progress xdist hooks validate.

	if (-not $enableQt) {
		$args += @('-p', 'no:pytest-qt')
	}

	if ($env:LIB_PYTEST_FULL -eq 'true' -and (Test-Path (Join-Path $RepoRoot 'src'))) {
		if ($Bucket -eq 'core') {
			$args += @('--cov=src', '--cov-report=term-missing:skip-covered', '-ra', '--tb=short')
		}
		else {
			$args += @('--cov=src', '--cov-append', '--cov-report=term-missing:skip-covered', '-ra', '--tb=short')
		}
	}
	else {
		$args += @('-p', 'no:pytest_cov')
	}

	if ($env:CI -ne 'true' -and $env:LIB_PYTEST_FULL -ne 'true' -and $result.TestmonFile) {
		$result.EnvPairs += ("TESTMON_DATAFILE={0}" -f $result.TestmonFile)
		$args += @('--testmon-forceselect', '--ff')
	}

	if ($env:LIB_GATE_TIMINGS -eq 'true') {
		$args += '--durations=25'
	}

	$result.Args = $args
	return $result
}

function Set-EnvPairs {
	param([string[]] $Pairs)
	$saved = @{}
	foreach ($pair in @($Pairs)) {
		if ([string]::IsNullOrWhiteSpace($pair)) { continue }
		$idx = $pair.IndexOf('=')
		if ($idx -lt 1) { continue }
		$key = $pair.Substring(0, $idx)
		$val = $pair.Substring($idx + 1)
		$saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
		[Environment]::SetEnvironmentVariable($key, $val, 'Process')
	}
	return $saved
}

function Restore-EnvPairs {
	param([hashtable] $Saved)
	if ($null -eq $Saved) { return }
	foreach ($key in $Saved.Keys) {
		$val = $Saved[$key]
		if ($null -eq $val) {
			[Environment]::SetEnvironmentVariable($key, $null, 'Process')
		}
		else {
			[Environment]::SetEnvironmentVariable($key, $val, 'Process')
		}
	}
}

function Get-QuietPytestArgs {
	$quietArgs = @()
	if ($env:LIB_GATE_QUIET -eq 'true') {
		$quietArgs = @('-q', '--no-header', '-ra', '--tb=short', '-p', 'agent_progress')
		$sep = ';'
		if ($env:PYTHONPATH) {
			$env:PYTHONPATH = "$InternalDir$sep$($env:PYTHONPATH)"
		}
		else {
			$env:PYTHONPATH = $InternalDir
		}
	}
	return $quietArgs
}

function Invoke-PytestOnce {
	param([string[]] $PytestArgs)
	$script:LastPytestExit = 1
	Push-Location -LiteralPath $RepoRoot
	try {
		# Do not pipe through ForEach-Object - let the child inherit stdout/stderr.
		if (Test-Path -LiteralPath $VenvPython) {
			& $VenvPython -m pytest @PytestArgs
			$script:LastPytestExit = [int]$LASTEXITCODE
		}
		else {
			$prev = $env:UV_NO_SYNC
			$env:UV_NO_SYNC = '1'
			try {
				& uv run -- pytest @PytestArgs
				$script:LastPytestExit = [int]$LASTEXITCODE
			}
			finally {
				if ($null -eq $prev) { Remove-Item Env:UV_NO_SYNC -ErrorAction SilentlyContinue }
				else { $env:UV_NO_SYNC = $prev }
			}
		}
	}
	finally {
		Pop-Location
	}
}

function Invoke-OneBucket {
	param([string] $Bucket)
	$spec = Get-BucketPytestArgs -Bucket $Bucket
	if ($spec.Empty) {
		Write-GateHost "pytest[${Bucket}]: skipped (no paths)"
		$script:LastPytestExit = 0
		return
	}

	$envPairs = @($spec.EnvPairs)
	if ($env:LIB_GATE_QUIET -eq 'true' -and $Bucket -eq 'heavy') {
		$envPairs += @(
			'LIB_PYTEST_PROGRESS_INTERVAL=1'
			'HF_HUB_DISABLE_PROGRESS_BARS=1'
			'TRANSFORMERS_VERBOSITY=error'
			'TQDM_DISABLE=1'
		)
	}

	$quietArgs = Get-QuietPytestArgs
	$pytestArgs = @($spec.Args) + @($quietArgs)

	Write-GateHost ("pytest[{0}]: args: {1}" -f $Bucket, ($pytestArgs -join ' '))
	Write-GateHost ("pytest[{0}]: env: {1}" -f $Bucket, ($envPairs -join ' '))

	$saved = Set-EnvPairs -Pairs $envPairs
	$prevUnbuf = $env:PYTHONUNBUFFERED
	$env:PYTHONUNBUFFERED = '1'
	try {
		Invoke-PytestOnce -PytestArgs $pytestArgs
	}
	finally {
		$env:PYTHONUNBUFFERED = $prevUnbuf
		Restore-EnvPairs -Saved $saved
	}
}

function Stop-ProcessTree {
	param([System.Diagnostics.Process] $Process)
	if ($null -eq $Process) { return }
	try {
		if (-not $Process.HasExited) {
			& taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
		}
	}
	catch { }
	try {
		if (-not $Process.HasExited) {
			Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
		}
	}
	catch { }
}

function Wait-GateProcess {
	param(
		[System.Diagnostics.Process] $Process,
		[int] $TimeoutSeconds = 0
	)
	if ($null -eq $Process) { return 1 }
	if ($TimeoutSeconds -gt 0) {
		Wait-Process -InputObject $Process -Timeout $TimeoutSeconds -ErrorAction SilentlyContinue
		if (-not $Process.HasExited) {
			Stop-ProcessTree -Process $Process
			try { $Process.WaitForExit(5000) | Out-Null } catch { }
			return 124
		}
	}
	else {
		Wait-Process -InputObject $Process -ErrorAction SilentlyContinue
	}
	try {
		return [int]$Process.ExitCode
	}
	catch {
		return 1
	}
}

function Get-GatePowerShellExe {
	$pwsh = Get-Command 'pwsh' -ErrorAction SilentlyContinue
	if ($pwsh) { return $pwsh.Source }
	return (Join-Path $PSHome 'powershell.exe')
}

function Start-GateChildProcess {
	param(
		[string[]] $ChildArgs,
		[string] $LogPath,
		[string] $ErrPath
	)
	$psExe = Get-GatePowerShellExe
	$argList = @(
		'-NoProfile'
		'-ExecutionPolicy', 'Bypass'
		'-File', $PSCommandPathResolved
	) + $ChildArgs

	$startParams = @{
		FilePath               = $psExe
		ArgumentList           = $argList
		WorkingDirectory       = $RepoRoot
		NoNewWindow            = $true
		PassThru               = $true
		RedirectStandardOutput = $LogPath
		RedirectStandardError  = $ErrPath
	}
	return Start-Process @startParams
}

function Merge-GateLogs {
	param([string] $OutPath, [string] $ErrPath, [string] $DestPath)
	$lines = @()
	if (Test-Path -LiteralPath $OutPath) {
		$lines += Get-Content -LiteralPath $OutPath -ErrorAction SilentlyContinue
	}
	if (Test-Path -LiteralPath $ErrPath) {
		$lines += Get-Content -LiteralPath $ErrPath -ErrorAction SilentlyContinue
	}
	Set-Content -LiteralPath $DestPath -Value $lines -Encoding UTF8
}

function Show-GateLogIfNeeded {
	param([string] $LogPath, [string] $Status)
	$quiet = ($env:LIB_GATE_QUIET -eq 'true')
	if ($quiet -and $Status -ne 'FAIL') { return }
	if (Test-Path -LiteralPath $LogPath) {
		Get-Content -LiteralPath $LogPath -ErrorAction SilentlyContinue | Write-Host
	}
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
	Write-Host (' {0,-17} {1,-8} {2,7} {3,9} {4,8}' -f 'Step', 'Status', 'Errors', 'Warnings', 'Seconds')
	Write-Host (' ' + ('-' * 54))
	for ($i = 0; $i -lt $script:GateReport.Count; $i++) {
		$row = $script:GateReport[$i]
		$label = switch ($row['Status']) {
			'pass' { 'pass' }
			'warn' { 'WARN' }
			'FAIL' { 'FAIL' }
			'skip' { 'skip' }
			default { $row['Status'] }
		}
		$secs = 0
		if ($row.ContainsKey('Seconds')) { $secs = [int]$row['Seconds'] }
		Write-Host (' [{0}] {1,-14} {2,-8} {3,7} {4,9} {5,8}' -f ($i + 1), $row['Name'], $label, $row['Errors'], $row['Warnings'], $secs)
	}
	Write-Host (' ' + ('-' * 54))
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
			Invoke-VenvOrUv -Name 'ruff' -ToolArgs (@('check') + $targets + @('--fix'))
			if ($script:LastToolExit -ne 0) {
				Write-GateGhaError 'ruff' "ruff fix failed (exit $($script:LastToolExit))"
				Complete-GateStep -Status FAIL -Errors 1 -Details @("[ruff] exit $($script:LastToolExit)")
				return
			}
			Invoke-VenvOrUv -Name 'ruff' -ToolArgs (@('format') + $targets)
			if ($script:LastToolExit -ne 0) {
				Complete-GateStep -Status FAIL -Errors 1 -Details @("[ruff] format exit $($script:LastToolExit)")
				return
			}
			Complete-GateStep -Status pass
			return
		}

		$ruffExe = Get-VenvExe -Name 'ruff'
		if ($ruffExe) {
			$checkOut = & $ruffExe check @targets --output-format=github 2>&1 | ForEach-Object { "$_" }
		}
		else {
			$checkOut = & uv run -- ruff check @targets --output-format=github 2>&1 | ForEach-Object { "$_" }
		}
		foreach ($line in $checkOut) { Write-GateHost $line }

		$errors = 0
		$warnings = 0
		if (Test-Path -LiteralPath $EmitPy) {
			$emitOut = @()
			if (Test-Path -LiteralPath $VenvPython) {
				$emitOut = $checkOut | & $VenvPython $EmitPy ruff-github 2>&1 | ForEach-Object { "$_" }
			}
			else {
				$emitOut = $checkOut | & uv run -- python $EmitPy ruff-github 2>&1 | ForEach-Object { "$_" }
			}
			foreach ($line in $emitOut) {
				if ($line -like 'GATE_SUMMARY*') {
					if ($line -match 'errors=(\d+)') { $errors = [int]$Matches[1] }
					if ($line -match 'warnings=(\d+)') { $warnings = [int]$Matches[1] }
				}
				elseif ($line -like '::*') { Write-GateHost $line }
			}
		}
		elseif ($LASTEXITCODE -ne 0) {
			$errors = 1
		}

		if ($ruffExe) {
			$fmtOut = & $ruffExe format --check @targets 2>&1 | ForEach-Object { "$_" }
		}
		else {
			$fmtOut = & uv run -- ruff format --check @targets 2>&1 | ForEach-Object { "$_" }
		}
		$fmtExit = [int]$LASTEXITCODE
		if ($fmtOut) { foreach ($line in $fmtOut) { Write-GateHost $line } }
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
	# Test tools FIRST - before any directory walk.
	$hasShellcheck = Test-Cmd 'shellcheck'
	$hasShfmt = Test-Cmd 'shfmt'
	if (-not $hasShellcheck -or -not $hasShfmt) {
		$missing = @()
		if (-not $hasShellcheck) { $missing += 'shellcheck' }
		if (-not $hasShfmt) { $missing += 'shfmt' }
		Write-GateHost "note: skipping shell step (missing: $($missing -join ', '))"
		Write-GateHost 'Install shellcheck + shfmt (scoop/choco) to lint .sh scripts on Windows.'
		Complete-GateStep -Status warn -Warnings 1 -Details @("[shell] skipped; missing $($missing -join ', ')")
		return
	}

	$scripts = @(Get-ShellScripts)
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
			$pyrightExe = Get-VenvExe -Name 'basedpyright'
			if ($pyrightExe) {
				$json = & $pyrightExe --outputjson 2>$stderrFile
			}
			else {
				$json = & uv run -- basedpyright --outputjson 2>$stderrFile
			}
			$exit = [int]$LASTEXITCODE
			$emitOut = @()
			if (Test-Path -LiteralPath $EmitPy) {
				if (Test-Path -LiteralPath $VenvPython) {
					$emitOut = ($json | & $VenvPython $EmitPy pyright 2>&1 | ForEach-Object { "$_" })
				}
				else {
					$emitOut = ($json | & uv run -- python $EmitPy pyright 2>&1 | ForEach-Object { "$_" })
				}
			}
			$summary = $null
			foreach ($line in $emitOut) {
				if ($line -like 'GATE_SUMMARY*') { $summary = $line }
				elseif ($line -like '::*') {
					Write-GateHost $line
					if ($line -match 'invalid JSON' -and (Get-Item $stderrFile).Length -gt 0) {
						Get-Content -LiteralPath $stderrFile | ForEach-Object { Write-GateHost $_ }
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
		$lockPath = Join-Path $RepoRoot 'uv.lock'
		$lockHash = ''
		if (Test-Path -LiteralPath $lockPath) {
			$lockHash = Get-FileSha256 -Path $lockPath
			if (Test-GateCacheHit -Name 'pip-audit' -Hash $lockHash -MaxAgeDays 7) {
				Write-GateHost 'note: skipping pip-audit (uv.lock unchanged, cache hit)'
				Complete-GateStep -Status skip
				return
			}
		}

		$pythonBin = $VenvPython
		if (-not (Test-Path -LiteralPath $pythonBin)) {
			$pythonBin = (& uv run -- python -c 'import sys; print(sys.executable)').Trim()
		}
		if (-not $pythonBin) {
			Complete-GateStep -Status FAIL -Errors 1 -Details @('[pip-audit] could not resolve python')
			return
		}
		$env:PIPAPI_PYTHON_LOCATION = $pythonBin
		Invoke-VenvOrUv -Name 'pip-audit' -ToolArgs @('--skip-editable')
		if ($script:LastToolExit -eq 0) {
			if ($lockHash) { Save-GateCache -Name 'pip-audit' -Hash $lockHash }
			Complete-GateStep -Status pass
		}
		else {
			Write-GateGhaError 'pip-audit' "dependency audit failed (exit $($script:LastToolExit))"
			Complete-GateStep -Status FAIL -Errors 1 -Details @("[pip-audit] exit $($script:LastToolExit)")
		}
	}
}

function Invoke-BuildStep {
	$pyproject = Join-Path $RepoRoot 'pyproject.toml'
	$buildHash = ''
	if (Test-Path -LiteralPath $pyproject) {
		$buildHash = Get-FileSha256 -Path $pyproject
		if (Test-GateCacheHit -Name 'build' -Hash $buildHash -MaxAgeDays 7) {
			Write-GateHost 'note: skipping wheel build (pyproject.toml unchanged, cache hit)'
			Complete-GateStep -Status skip
			return
		}
	}

	$buildDir = Join-Path ([System.IO.Path]::GetTempPath()) ("srxy-build-" + [guid]::NewGuid().ToString('n'))
	New-Item -ItemType Directory -Path $buildDir | Out-Null
	try {
		Invoke-InRepo {
			$prev = $env:UV_NO_SYNC
			$env:UV_NO_SYNC = '1'
			try {
				& uv build --wheel --out-dir $buildDir
				$code = [int]$LASTEXITCODE
			}
			finally {
				if ($null -eq $prev) { Remove-Item Env:UV_NO_SYNC -ErrorAction SilentlyContinue }
				else { $env:UV_NO_SYNC = $prev }
			}
			$wheels = @(Get-ChildItem -LiteralPath $buildDir -Filter '*.whl' -File -ErrorAction SilentlyContinue)
			if ($code -ne 0 -or $wheels.Count -eq 0) {
				Write-GateGhaError 'build' "package build failed (exit $code)"
				Complete-GateStep -Status FAIL -Errors 1 -Details @("[build] exit $code")
				return
			}
			Write-GateHost "Built $($wheels.Count) wheel(s):"
			$wheels | ForEach-Object { Write-GateHost $_.FullName }
			if ($buildHash) { Save-GateCache -Name 'build' -Hash $buildHash }
			Complete-GateStep -Status pass
		}
	}
	finally {
		Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
	}
}

function Invoke-PytestBucketsInline {
	# Sequential or concurrent buckets in-process (Fix path / serial mode).
	$serialize = ($env:LIB_GATE_BUCKET_CONCURRENCY -eq '1') -or ($script:SelectedBuckets.Count -le 1)
	$overall = 0

	if ($serialize) {
		foreach ($bucket in $script:SelectedBuckets) {
			Invoke-OneBucket -Bucket $bucket
			$code = $script:LastPytestExit
			if ($code -ne 0) {
				$overall = $code
				break
			}
		}
		$script:LastPytestExit = $overall
		return
	}

	$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("srxy-pytest-" + [guid]::NewGuid().ToString('n'))
	New-Item -ItemType Directory -Path $tmp | Out-Null
	$env:LIB_GATE_ACTIVE_BUCKETS = "$($script:SelectedBuckets.Count)"
	$wall = Get-PytestWallSeconds
	$procs = @{}
	$logs = @{}
	$started = @{}

	try {
		foreach ($bucket in $script:SelectedBuckets) {
			$log = Join-Path $tmp "$bucket.log"
			$err = Join-Path $tmp "$bucket.err"
			$status = Join-Path $tmp "$bucket.status"
			$logs[$bucket] = $log
			$started[$bucket] = Get-Date
			$procs[$bucket] = Start-GateChildProcess -ChildArgs @(
				'-InternalBucket', $bucket
				'-InternalStatus', $status
			) -LogPath $log -ErrPath $err
		}
		foreach ($bucket in $script:SelectedBuckets) {
			$code = Wait-GateProcess -Process $procs[$bucket] -TimeoutSeconds $wall
			$merged = Join-Path $tmp "$bucket.merged.log"
			Merge-GateLogs -OutPath $logs[$bucket] -ErrPath (Join-Path $tmp "$bucket.err") -DestPath $merged
			Write-Host ''
			Write-Host ("---- pytest[{0}] (exit {1}) ----" -f $bucket, $code)
			if (Test-Path -LiteralPath $merged) {
				Get-Content -LiteralPath $merged -ErrorAction SilentlyContinue | Write-Host
			}
			if ($code -ne 0 -and $overall -eq 0) { $overall = $code }
		}
	}
	finally {
		Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
	}
	$script:LastPytestExit = $overall
}

function Invoke-PytestStep {
	Write-Host ("pytest buckets: {0} ({1})" -f ($script:SelectedBuckets -join ' '), $script:ScopeReason)
	if ($env:LIB_GATE_BUCKET_CONCURRENCY -eq '1') {
		Write-Host 'note: LIB_GATE_BUCKET_CONCURRENCY=1 - buckets run serially'
	}
	if ([string]::IsNullOrWhiteSpace($env:LIB_PYTEST_WORKERS)) {
		$env:LIB_PYTEST_WORKERS = "$(Get-PytestWorkers)"
	}
	Invoke-PytestBucketsInline
	$code = $script:LastPytestExit
	if ($code -ne 0) {
		Write-GateGhaError 'pytest' "tests failed (exit $code)"
		Complete-GateStep -Status FAIL -Errors 1 -Details @("[pytest] exit $code")
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
	$script:GateLogFile = $null
	$script:GateStepStart = Get-Date
	# Prefer writing tool output via redirected stdout from parent; GateHost for messages.
	if (-not [string]::IsNullOrWhiteSpace($InternalLog)) {
		$script:GateLogFile = $InternalLog
		if (-not (Test-Path -LiteralPath $InternalLog)) {
			Set-Content -LiteralPath $InternalLog -Value @() -Encoding UTF8
		}
	}
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

# --- internal one-bucket mode ---
if (-not [string]::IsNullOrWhiteSpace($InternalBucket)) {
	$script:StatusFile = $InternalStatus
	$script:GateStepStart = Get-Date
	try {
		Invoke-OneBucket -Bucket $InternalBucket
		$code = $script:LastPytestExit
		if ($code -eq 0) {
			Complete-GateStep -Status pass
		}
		else {
			Complete-GateStep -Status FAIL -Errors 1 -Details @("[pytest][$InternalBucket] exit $code")
		}
		exit $code
	}
	catch {
		Complete-GateStep -Status FAIL -Errors 1 -Details @("[gate] $($_.Exception.Message)")
		exit 1
	}
}

# --- main gate ---
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.venv'))) {
	Write-Host 'Missing .venv. Create it first: uv run task sync-win  (or: uv sync --extra semantic --extra windows)' -ForegroundColor Red
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

if ($Full -and -not $script:ScopeSet) {
	$Scope = 'all'
}

$env:LIB_PYTEST_FULL = $(if ($Full) { 'true' } else { 'false' })
$env:LIB_PYTEST_FULL_CPU = $(if ($FullCpu) { 'true' } else { 'false' })
$env:LIB_GATE_QUIET = $(if ($Quiet) { 'true' } else { 'false' })
$env:LIB_GATE_TIMINGS = $(if ($Timings) { 'true' } else { 'false' })
$env:LIB_GATE_NO_CACHE = $(if ($NoCache) { 'true' } else { 'false' })
$env:LIB_GATE_SCOPE = $Scope

Resolve-GateBuckets
Write-Host ("scope: {0} ({1})" -f ($script:SelectedBuckets -join ' '), $script:ScopeReason)

# Windows uv sync installs CPU-only torch; restore CUDA wheels before heavy work.
if (
	$script:SelectedBuckets -contains 'heavy' -and
	$env:GITHUB_ACTIONS -ne 'true' -and
	$env:SRXY_SKIP_CUDA_TORCH -ne '1'
) {
	$ensureCuda = Join-Path $RepoRoot 'scripts\dev\ensure-windows-cuda-torch.ps1'
	if (Test-Path -LiteralPath $ensureCuda) {
		Write-Host 'gate: ensuring CUDA PyTorch for heavy bucket (uv sync leaves CPU-only torch on Windows)...'
		& $ensureCuda
		if ($LASTEXITCODE -ne 0) {
			Write-Host "gate: ensure-windows-cuda-torch failed (exit $LASTEXITCODE). Heavy tests would run on CPU." -ForegroundColor Red
			Write-Host 'Fix: uv run task sync-win   or set SRXY_SKIP_CUDA_TORCH=1 to bypass.' -ForegroundColor Red
			exit $LASTEXITCODE
		}
	}
}

$hasPytest = Test-Path -LiteralPath (Join-Path $RepoRoot 'tests')
if ($hasPytest) {
	$script:GatePlannedSteps = 5 + $script:SelectedBuckets.Count
}
else {
	$script:GatePlannedSteps = 5
}

# Worker budget: reserve a core per concurrent non-core bucket; serial => active=1.
if ([string]::IsNullOrWhiteSpace($env:LIB_PYTEST_WORKERS)) {
	$concurrent = ($hasPytest -and $script:SelectedBuckets.Count -gt 1 -and $env:LIB_GATE_BUCKET_CONCURRENCY -ne '1' -and -not $Fix)
	if ($concurrent) {
		$env:LIB_GATE_ACTIVE_BUCKETS = "$($script:SelectedBuckets.Count)"
	}
	else {
		$env:LIB_GATE_ACTIVE_BUCKETS = '1'
	}
	$env:LIB_PYTEST_WORKERS = "$(Get-PytestWorkers)"
}

Acquire-GateLock
try {
	Set-Location -LiteralPath $RepoRoot

	if ($Fix) {
		foreach ($name in @('ruff', 'shell', 'basedpyright', 'pip-audit', 'build')) {
			Start-GateStep $name
			Invoke-NamedStep -Name $name -DoFix:$true
		}
		if ($hasPytest) {
			# One report row per bucket (matches planned step count).
			foreach ($bucket in $script:SelectedBuckets) {
				Start-GateStep ("pytest[{0}]" -f $bucket)
				Invoke-OneBucket -Bucket $bucket
				$code = $script:LastPytestExit
				if ($code -ne 0) {
					Write-GateGhaError 'pytest' "tests failed (exit $code)"
					Complete-GateStep -Status FAIL -Errors 1 -Details @("[pytest][$bucket] exit $code")
					# Continue remaining buckets for fuller report, or break? Bash breaks on Fix single pytest.
					# Keep going so all selected buckets are reported.
				}
				else {
					Complete-GateStep -Status pass
				}
			}
		}
	}
	else {
		$parallelDir = Join-Path ([System.IO.Path]::GetTempPath()) ("srxy-gate-" + [guid]::NewGuid().ToString('n'))
		New-Item -ItemType Directory -Path $parallelDir | Out-Null
		try {
			Write-Host ("Parallel verify (light steps overlapping pytest buckets; workers={0})" -f $env:LIB_PYTEST_WORKERS)

			$wall = Get-PytestWallSeconds
			$lightNames = @('ruff', 'shell', 'basedpyright', 'pip-audit', 'build')
			$lightProcs = @{}
			$lightStarted = @{}
			$bucketProcs = @{}
			$bucketStarted = @{}
			$serializeBuckets = ($env:LIB_GATE_BUCKET_CONCURRENCY -eq '1')

			# Start pytest buckets first so they overlap light steps.
			if ($hasPytest) {
				if ($serializeBuckets) {
					Write-Host 'note: LIB_GATE_BUCKET_CONCURRENCY=1 - buckets run serially (after light wait)'
				}
				else {
					$env:LIB_GATE_ACTIVE_BUCKETS = "$($script:SelectedBuckets.Count)"
					foreach ($bucket in $script:SelectedBuckets) {
						$log = Join-Path $parallelDir "bucket-$bucket.log"
						$err = Join-Path $parallelDir "bucket-$bucket.err"
						$status = Join-Path $parallelDir "bucket-$bucket.status"
						$bucketStarted[$bucket] = Get-Date
						$bucketProcs[$bucket] = Start-GateChildProcess -ChildArgs @(
							'-InternalBucket', $bucket
							'-InternalStatus', $status
						) -LogPath $log -ErrPath $err
					}
				}
			}

			foreach ($name in $lightNames) {
				$log = Join-Path $parallelDir "$name.log"
				$err = Join-Path $parallelDir "$name.err"
				$status = Join-Path $parallelDir "$name.status"
				$lightStarted[$name] = Get-Date
				$lightProcs[$name] = Start-GateChildProcess -ChildArgs @(
					'-InternalStep', $name
					'-InternalStatus', $status
					'-InternalLog', (Join-Path $parallelDir "$name.host.log")
				) -LogPath $log -ErrPath $err
			}

			# Wait for light steps (no wall watchdog).
			foreach ($name in $lightNames) {
				[void](Wait-GateProcess -Process $lightProcs[$name] -TimeoutSeconds 0)
			}

			# Finish light steps in order.
			foreach ($name in $lightNames) {
				$merged = Join-Path $parallelDir "$name.merged.log"
				$hostLog = Join-Path $parallelDir "$name.host.log"
				Merge-GateLogs -OutPath (Join-Path $parallelDir "$name.log") -ErrPath (Join-Path $parallelDir "$name.err") -DestPath $merged
				if (Test-Path -LiteralPath $hostLog) {
					Add-Content -LiteralPath $merged -Value (Get-Content -LiteralPath $hostLog -ErrorAction SilentlyContinue) -Encoding UTF8
				}
				$fallbackSec = 0
				if ($lightStarted.ContainsKey($name)) {
					$fallbackSec = [int][Math]::Max(0, ((Get-Date) - $lightStarted[$name]).TotalSeconds)
				}
				Start-GateStep $name
				Import-GateStatusFile -File (Join-Path $parallelDir "$name.status") -FallbackSeconds $fallbackSec
				$row = $script:GateReport[$script:GateCurrentIndex]
				Show-GateLogIfNeeded -LogPath $merged -Status $row['Status']
			}

			if ($hasPytest) {
				if ($serializeBuckets) {
					foreach ($bucket in $script:SelectedBuckets) {
						Start-GateStep ("pytest[{0}]" -f $bucket)
						Invoke-OneBucket -Bucket $bucket
						$code = $script:LastPytestExit
						if ($code -ne 0) {
							Write-GateGhaError 'pytest' "tests failed (exit $code)"
							Complete-GateStep -Status FAIL -Errors 1 -Details @("[pytest][$bucket] exit $code")
						}
						else {
							Complete-GateStep -Status pass
						}
					}
				}
				else {
					foreach ($bucket in $script:SelectedBuckets) {
						$code = Wait-GateProcess -Process $bucketProcs[$bucket] -TimeoutSeconds $wall
						$merged = Join-Path $parallelDir "bucket-$bucket.merged.log"
						Merge-GateLogs -OutPath (Join-Path $parallelDir "bucket-$bucket.log") `
							-ErrPath (Join-Path $parallelDir "bucket-$bucket.err") `
							-DestPath $merged
						$fallbackSec = 0
						if ($bucketStarted.ContainsKey($bucket)) {
							$fallbackSec = [int][Math]::Max(0, ((Get-Date) - $bucketStarted[$bucket]).TotalSeconds)
						}
						Start-GateStep ("pytest[{0}]" -f $bucket)
						# Record from process exit code (authoritative). Child status
						# files are best-effort; do not leave rows as pending.
						if ($code -eq 124) {
							Complete-GateStep -Status FAIL -Errors 1 -Details @("[pytest][$bucket] wall timeout (${wall}s) -> exit 124") -Seconds $fallbackSec
						}
						elseif ($code -ne 0) {
							$extra = @("[pytest][$bucket] exit $code")
							$statusFile = Join-Path $parallelDir "bucket-$bucket.status"
							if (Test-Path -LiteralPath $statusFile) {
								Get-Content -LiteralPath $statusFile -ErrorAction SilentlyContinue | ForEach-Object {
									if ($_ -match '^detail=(.*)$') { $extra += $Matches[1] }
								}
							}
							Complete-GateStep -Status FAIL -Errors 1 -Details $extra -Seconds $fallbackSec
						}
						else {
							Complete-GateStep -Status pass -Seconds $fallbackSec
						}
						Write-Host ''
						Write-Host ("---- pytest[{0}] (exit {1}) ----" -f $bucket, $code)
						if (Test-Path -LiteralPath $merged) {
							Get-Content -LiteralPath $merged -ErrorAction SilentlyContinue | Write-Host
						}
						if ($code -ne 0) {
							Write-GateGhaError 'pytest' "tests failed (exit $code)"
						}
					}
				}
			}
		}
		finally {
			Remove-Item -LiteralPath $parallelDir -Recurse -Force -ErrorAction SilentlyContinue
		}
	}

	Show-GateReport
	if ($script:GateTotalErrors -gt 0) { exit 1 }
	exit 0
}
finally {
	Release-GateLock
}
