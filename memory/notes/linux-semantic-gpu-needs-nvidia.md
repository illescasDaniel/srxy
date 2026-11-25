---
name: linux-semantic-gpu-needs-nvidia
description: (1) Linux matches Windows: semantic-gpu only when NVIDIA is detected (same skip envs). No GPU → --extra semantic. (2) Document that GitHub Actions keeps…
type: decision
date: 2026-08-30
status: superseded
supersedes: 
superseded_by: semantic-extra-gpu-only
source:
---
- **Context:** First cut of `sync-dev` always used `--extra semantic-gpu` on Linux. CI never needed torch extras for `core+gui+tui`.
- **Decision:** (1) Linux matches Windows: `semantic-gpu` only when NVIDIA is detected (same skip envs). No GPU → `--extra semantic`. (2) Document that GitHub Actions keeps `uv sync --frozen` (no `[semantic]` / `[semantic-gpu]`); CI does not run the heavy suite.
- **Rationale:** Avoid multi-GiB CUDA wheels on CPU-only Linux laptops; CI stays lean and already omitted semantic extras.
