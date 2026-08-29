# Active Context

_Last updated: 2026-08-29_

## Branch

- Worktree `9x6r` / `cursor/943ab584` — quality-gate speedup + Windows CUDA-torch ensure (apply-worktree paused).

## Current focus

- Fixed CPU-only torch in this worktree's `.venv` (`2.13.0+cu130`, cuda=True on RTX 4070).
- Docs/skills/gate hook added so `uv sync` cannot silently leave heavy tests on CPU again.
- `/apply-worktree-srxy` was interrupted for this GPU fix — resume when asked.

## Done this session

- Diagnosed `torch 2.13.0+cpu` despite NVIDIA GPU; `uv sync` proven to wipe CUDA wheels.
- Installed CUDA torch; added `scripts/dev/ensure-windows-cuda-torch.ps1`, `sync-win.ps1`/`.cmd`, Taskipy `sync-win`, gate auto-ensure on `heavy`, AGENTS/docs/skill updates.

## Next steps

1. Resume `/apply-worktree-srxy` when user asks (commit this GPU-fix work on the worktree branch first if dirty).
2. Optional: push branch / open PR into `feature/fixes_1.6.6` when asked.
