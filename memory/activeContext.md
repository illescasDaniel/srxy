# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Just finished: **Linux validation of Windows-merged quality gate** + **Unix `copy-venv.sh`** for the copy-venv-to-worktree-srxy skill.

## Touched files

- `.cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv.sh` — new bash twin of `copy-venv-win.ps1` (rsync + `uv sync --extra semantic`)
- `.cursor/skills/copy-venv-to-worktree-srxy/SKILL.md` — Unix section invokes the script (not inline snippet)
- `scripts/quality/checks.sh` — SC2155: declare/assign `LIB_PYTEST_WORKERS` separately
- `scripts/quality/internal/lib.sh` — drop unused `cov_append`; SC2034 disable on `LIB_SCOPE_REASON`
- `memory/activeContext.md`, `memory/progress.md`

## Verified

- `bash …/copy-venv.sh` from primary → exit 0 “Already in the primary checkout”; shellcheck + shfmt clean
- `uv run task checks-fix-quiet` PASSED (after shellcheck fixes; full pytest earlier in session: heavy 45, gui 167+1 skip, tui 90, core 671+1 skip)
- `uv run task checks-all-quiet` PASSED

## Manual QA (user)

- **Verify installers after 1.7.0 changes**, especially the **Windows offline installer**: Recommended (GPU) should install CUDA PyTorch into the prefix `.venv` (`+cu130` / `torch.cuda.is_available()` True on NVIDIA). Also smoke macOS/Linux installers for 1.7.0 regressions (splash, theme, semantic option).
- Note: this Linux host currently has `nvidia-smi` driver failure (`cuda=False` despite `2.13.0+cu130` in venv) — environmental, not a code bug.

## Next steps

1. Commit copy-venv Unix script + shellcheck gate fixes (+ memory) when ready.
2. User: manual Windows (and other) installer verification for 1.7.0.
3. `/delete-worktree-srxy` for applied worktrees when ready.
4. Final QA / release for 1.7.0 when ready.
