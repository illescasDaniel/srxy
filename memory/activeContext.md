# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0**.

## Current focus

Just finished: **`semantic-gpu` extra** so Windows `sync-win` no longer uninstalls/reinstalls CUDA torch on every sync.

## Touched files

- `pyproject.toml` — `semantic-gpu` extra; `[[tool.uv.index]]` pytorch-cu130; `[tool.uv.sources]` for torch/torchvision/torchaudio on win32; sync-win task help
- `uv.lock` — regenerated (`2.13.0+cu130` / torchvision / torchaudio for Windows)
- `scripts/dev/sync-win.ps1` — GPU-conditional `--extra semantic-gpu` vs `semantic`
- `scripts/dev/ensure-windows-cuda-torch.ps1` — docstring / missing-venv hint
- `AGENTS.md`, `docs/development.md`, `docs/installation.md`, `.cursor/skills/apply-worktree-srxy/SKILL.md`
- `memory/decisions.md`, `memory/progress.md`, `memory/activeContext.md`

## Verified

- `uv run task sync-win` → `Checked 121 packages in 13ms` (no torch uninstall) + `ensure-windows-cuda-torch: OK (2.13.0+cu130, cuda=True)`

## Manual QA (user)

- **Verify installers after 1.7.0 changes**, especially the **Windows offline installer**: Recommended (GPU) should install CUDA PyTorch into the prefix `.venv` (`+cu130` / `torch.cuda.is_available()` True on NVIDIA). Also smoke macOS/Linux installers for 1.7.0 regressions (splash, theme, semantic option).

## Next steps

1. Commit `semantic-gpu` / lockfile / sync-win / docs when ready.
2. User: manual Windows (and other) installer verification for 1.7.0.
3. `/delete-worktree-srxy` for applied worktrees when ready.
4. Final QA / release for 1.7.0 when ready.
