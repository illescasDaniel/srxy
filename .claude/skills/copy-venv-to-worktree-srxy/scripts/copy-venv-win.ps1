#Requires -Version 5.1
<#
.SYNOPSIS
  Copy .venv from the primary srxy checkout into the current worktree.

.DESCRIPTION
  Mirrors .venv from the primary checkout (the git worktree list entry that is
  NOT under %USERPROFILE%\.cursor\worktrees\) into the current worktree using
  robocopy, rewrites shebangs / editable .pth / direct_url.json / Windows
  trampoline UV_PYTHON_PATH for the new location, then runs uv sync to
  re-register the editable install.  No packages are re-downloaded.

  Intended to be run from any linked worktree root.  Devs can call it
  directly; agents invoke it via the copy-venv-to-worktree-srxy skill.

.PARAMETER Force
  Overwrite the destination .venv even if it already exists.

.EXAMPLE
  # From a freshly created worktree:
  powershell -ExecutionPolicy Bypass -File .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv-win.ps1

.EXAMPLE
  # Replace an existing (broken) .venv:
  powershell -ExecutionPolicy Bypass -File .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv-win.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---------------------------------------------------------------------------
# 1. Resolve current worktree root
# ---------------------------------------------------------------------------
$destRoot = & git rev-parse --show-toplevel 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not inside a git repository. Run this script from within a srxy worktree."
    exit 1
}
$destRoot = $destRoot.Trim() -replace '/', '\'

# ---------------------------------------------------------------------------
# 2. Parse git worktree list to find the primary checkout
# ---------------------------------------------------------------------------
$worktreeLines = & git worktree list 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "git worktree list failed: $worktreeLines"
    exit 1
}

$cursorWorktreesPattern = [System.IO.Path]::Combine($env:USERPROFILE, '.cursor', 'worktrees')

$primaryRoot = $null
foreach ($line in $worktreeLines) {
    $parts = $line -split '\s+'
    if (-not $parts[0]) { continue }
    $candidate = $parts[0].Trim() -replace '/', '\'
    # Primary checkout is never under %USERPROFILE%\.cursor\worktrees\
    if (-not $candidate.StartsWith($cursorWorktreesPattern, [System.StringComparison]::OrdinalIgnoreCase)) {
        $primaryRoot = $candidate
        break
    }
}

if (-not $primaryRoot) {
    Write-Error "Could not find the primary checkout in 'git worktree list'. Output was:`n$($worktreeLines -join "`n")"
    exit 1
}

# Normalise both to lowercase for comparison
if ($destRoot.TrimEnd('\') -ieq $primaryRoot.TrimEnd('\')) {
    Write-Host "Already in the primary checkout ($primaryRoot). Nothing to copy."
    exit 0
}

# ---------------------------------------------------------------------------
# 3. Validate source and destination
# ---------------------------------------------------------------------------
$srcVenv = Join-Path $primaryRoot '.venv'
$dstVenv = Join-Path $destRoot  '.venv'

if (-not (Test-Path $srcVenv)) {
    Write-Error @"
Source .venv not found at: $srcVenv
Run 'uv run task sync-dev' in the primary checkout first, then re-run this script.
"@
    exit 1
}

if ((Test-Path $dstVenv) -and -not $Force) {
    Write-Warning @"
Destination .venv already exists at: $dstVenv
Pass -Force to overwrite it, or delete it manually and re-run.
"@
    exit 1
}

if ((Test-Path $dstVenv) -and $Force) {
    Write-Host "copy-venv: removing existing destination .venv (--Force)..."
    Remove-Item -LiteralPath $dstVenv -Recurse -Force
}

# ---------------------------------------------------------------------------
# 4. robocopy mirror
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "copy-venv: copying .venv"
Write-Host "  from : $srcVenv"
Write-Host "  to   : $dstVenv"
Write-Host ""

# robocopy exit codes 0-7 are success (0=no change, 1=copied, etc.)
robocopy $srcVenv $dstVenv /E /NP /NFL /NDL /NJH /NJS
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -ge 8) {
    Write-Error "robocopy failed with exit code $robocopyExit"
    exit 1
}

Write-Host ""
Write-Host "copy-venv: copy complete (robocopy exit $robocopyExit)"

# ---------------------------------------------------------------------------
# 5. Rewrite shebangs / .pth / direct_url / trampoline UV_PYTHON_PATH
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "copy-venv: rewriting venv paths (shebangs, editable .pth, trampolines)..."
$dstPython = Join-Path $dstVenv 'Scripts\python.exe'
$rewriteScript = Join-Path $ScriptDir 'rewrite_venv_paths.py'
& $dstPython $rewriteScript --old-root $primaryRoot --new-root $destRoot
if ($LASTEXITCODE -ne 0) {
    Write-Error "rewrite_venv_paths.py failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

# ---------------------------------------------------------------------------
# 6. uv sync — re-register editable install
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "copy-venv: running platform-aware sync-dev (offline, reinstall srxy)..."
Set-Location -LiteralPath $destRoot
$syncPy = Join-Path $destRoot 'scripts\dev\sync.py'
& $dstPython $syncPy --offline --reinstall-package srxy
if ($LASTEXITCODE -ne 0) {
    Write-Host "copy-venv: offline sync failed (extras may need downloads); retrying online..."
    & $dstPython $syncPy --reinstall-package srxy
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "uv sync step failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

# ---------------------------------------------------------------------------
# 7. Verify editable import + torch
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "copy-venv: verifying paths..."
$srxyFile = & $dstPython -c "import srxy; print(srxy.__file__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "failed to import srxy from destination venv: $srxyFile"
    exit 1
}
$destSrcPrefix = (Join-Path $destRoot 'src').TrimEnd('\') + '\'
$srxyNorm = ([string]$srxyFile).Trim() -replace '/', '\'
if (-not $srxyNorm.StartsWith($destSrcPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Error "srxy.__file__ is not under worktree src/: $srxyFile"
    exit 1
}
Write-Host "  srxy.__file__: $srxyFile"

# Confirm pytest trampoline resolves via dest python (not primary).
$pytestExe = Join-Path $dstVenv 'Scripts\pytest.exe'
if (Test-Path -LiteralPath $pytestExe) {
    $pytestProbe = & $pytestExe --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pytest.exe from destination venv failed: $pytestProbe"
        exit 1
    }
    Write-Host "  pytest: $pytestProbe"
}

Write-Host ""
Write-Host "copy-venv: verifying torch..."
$torchCheck = & $dstPython -c `
    "import torch; print(torch.__version__, 'cuda=' + str(torch.cuda.is_available()))" `
    2>&1
Write-Host "  torch: $torchCheck"

Write-Host ""
Write-Host "copy-venv: done."
Write-Host "  source : $srcVenv"
Write-Host "  dest   : $dstVenv"
