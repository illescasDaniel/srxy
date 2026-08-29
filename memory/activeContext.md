# Active Context

_Last updated: 2026-08-29_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**. Applied worktree `9x6r` / `cursor/943ab584` (faster quality gate + Windows CUDA torch for sync-win and desktop installer).

## Current focus

None active — finish parent quality gate after merge; then optional `/delete-worktree-srxy` for `9x6r`.

## Manual QA (user)

- **Verify installers after 1.7.0 changes**, especially the **Windows offline installer**: Recommended (GPU) should install CUDA PyTorch into the prefix `.venv` (`+cu130` / `torch.cuda.is_available()` True on NVIDIA). Also smoke macOS/Linux installers for 1.7.0 regressions (splash, theme, semantic option).

## Next steps

1. Parent quality gate (`checks-win-fix-quiet` then `checks-win-quiet`).
2. User: manual Windows (and other) installer verification for 1.7.0.
3. `/delete-worktree-srxy` for applied worktrees when ready.
4. Final QA / release for 1.7.0 when ready.
