---
name: windows-cuda-torch-after-uv-sync
description: (1) Add scripts/dev/ensure-windows-cuda-torch.ps1 + sync-win task/cmd that sync then reinstall torch/torchvision/torchaudio from…
type: decision
date: 2026-08-29
status: superseded
supersedes: 
superseded_by: semantic-gpu-extra-windows-cuda
source:
---
- **Context:** On Windows, `uv sync --extra semantic` installs PyPI's CPU-only `torch…+cpu`. A later `uv sync` also **uninstalls** a previously installed CUDA wheel (`+cu130`) and restores CPU torch. Agents/gates then hit `warning: no GPU found; CLIP image semantic search will use CPU` despite an RTX GPU, making heavy tests far slower.
- **Decision:** (1) Add `scripts/dev/ensure-windows-cuda-torch.ps1` + `sync-win` task/cmd that sync then reinstall torch/torchvision/torchaudio from `https://download.pytorch.org/whl/cu130`. (2) `checks-win.ps1` runs the ensure script when the `heavy` bucket is selected (skipped in GitHub Actions / `SRXY_SKIP_CUDA_TORCH=1`). (3) Document in `AGENTS.md`, `docs/development.md`, `docs/installation.md`, and `apply-worktree-srxy`.
- **Rationale:** Cannot pin CUDA torch in the lockfile for all platforms without forcing multi-GiB CUDA wheels onto CI/macOS/CPU-only machines. Post-sync ensure is the durable Windows GPU workflow.
