---
name: semantic-extra-gpu-only
description: (1) Keep one optional extra named [semantic] whose deps are the former semantic-gpu stack (sentence-transformers, faster-whisper, rawpy, explicit…
type: decision
date: 2026-08-30
status: current
supersedes: semantic-gpu-extra-windows-cuda
superseded_by: 
source:
---
- **Context:** Offering a lighter CPU `[semantic]` alongside `[semantic-gpu]` encouraged installs that are too slow for real use, and the dual extras confused docs/`sync-dev`.
- **Decision:** (1) Keep one optional extra named `[semantic]` whose deps are the former `semantic-gpu` stack (sentence-transformers, faster-whisper, rawpy, explicit torch/torchaudio/torchvision, cublas markers). (2) Delete the old CPU-leaning semantic set and the `semantic-gpu` alias. (3) `sync.py` adds `--extra semantic` only for Linux/Windows NVIDIA or macOS Apple Silicon (MPS); no GPU / CUDA skip → no semantic extra. Also supersedes the earlier `linux-semantic-gpu-needs-nvidia` note.

(4) README/install docs: GPU rows use `srxy[semantic]`; remove “Fast CPU, no GPU”; no-GPU users get core-only.
- **Rationale:** Semantic search without a GPU is a poor default; one extra name matches user intent and keeps Windows CUDA via `[tool.uv.sources]` on checkout sync.
