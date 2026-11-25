---
name: windows-installer-cuda-pytorch
description: Add installer/cuda_torch.py and a cuda_torch install phase (after package) when semantic is selected on Windows and has_nvidia_gpu() is true. Reinstall…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Desktop/offline Windows installs used `uv pip install 'srxy[semantic,windows]'`, which resolves CPU-only torch from PyPI. GPU-recommended installs then ran CLIP/semantic on CPU despite NVIDIA detection for the setup type.
- **Decision:** Add `installer/cuda_torch.py` and a `cuda_torch` install phase (after package) when semantic is selected on Windows and `has_nvidia_gpu()` is true. Reinstall torch/torchvision/torchaudio from the PyTorch `cu130` index (`cu126` fallback). Dev checkouts keep `scripts/dev/ensure-windows-cuda-torch.ps1` / `sync-win`; the installer uses the Python helper (no PowerShell dependency for end users).
- **Rationale:** Same root cause as the agent/dev venv trap; end users cannot be expected to run a manual `uv pip` after Setup.
