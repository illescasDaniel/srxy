# Active Context

_Last updated: 2026-08-29_

## Branch

- Worktree `9x6r` / `cursor/943ab584` — applying into `feature/fixes_1.6.6` (CUDA torch for Windows installer + prior gate/sync-win work).

## Current focus

- `/apply-worktree-srxy` into main checkout.

## Manual QA (user)

- **Verify installers after 1.7.0 changes**, especially the **Windows offline installer**: Recommended (GPU) should install CUDA PyTorch into the prefix `.venv` (`+cu130` / `torch.cuda.is_available()` True on NVIDIA). Also smoke macOS/Linux installers for 1.7.0 regressions (splash, theme, semantic option).

## Next steps

1. Finish apply-worktree (merge + parent gate).
2. User: manual Windows (and other) installer verification for 1.7.0.
