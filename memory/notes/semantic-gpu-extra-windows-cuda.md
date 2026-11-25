---
name: semantic-gpu-extra-windows-cuda
description: (1) Add optional extra semantic-gpu = srxy[semantic] + explicit torch/torchaudio/torchvision. (2) [tool.uv.index] pytorch-cu130 (explicit = true) +…
type: decision
date: 2026-08-30
status: superseded
supersedes: windows-cuda-torch-after-uv-sync
superseded_by: semantic-extra-gpu-only
source:
---
- **Context:** `sync-win` always ran bare `uv sync --extra semantic` then `ensure-windows-cuda-torch.ps1`. Because the lockfile only had CPU PyPI torch, every sync uninstalled `+cu130` torch/torchvision/torchaudio and reinstalled CPU torch, then the ensure script re-downloaded CUDA wheels (~minutes / multi-GiB first time, still a full reinstall when already correct).
- **Decision:** (1) Add optional extra `semantic-gpu` = `srxy[semantic]` + explicit `torch`/`torchaudio`/`torchvision`. (2) `[tool.uv.index]` `pytorch-cu130` (`explicit = true`) + `[tool.uv.sources]` for those three packages with `marker = "sys_platform == 'win32'"`. (3) `sync-win.ps1` chooses `--extra semantic-gpu` when NVIDIA is present, else `--extra semantic`; keep ensure script as safety net. (4) Regenerate `uv.lock` so Windows resolves `2.13.0+cu130` etc.
- **Rationale:** Lockfile-owned CUDA wheels make `uv sync` a no-op when already installed (`Checked N packages`). Sources are Windows-only so macOS/Linux/CI keep PyPI. Windows-without-GPU may get the larger CUDA wheel if they use `semantic-gpu` or if transitive torch is resolved via sources for `semantic` — accepted (CUDA builds still run on CPU). Installer path unchanged (still post-pip ensure via `cuda_torch.py`).
