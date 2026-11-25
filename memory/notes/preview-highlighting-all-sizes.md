---
name: preview-highlighting-all-sizes
description: Remove the 16 KB / 500-line plain fallback entirely; always run the lightweight per-line tokenizer since preview payloads are already capped at…
type: decision
date: 2026-08-18
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** File-content preview fell back to unhighlighted "plain" rendering once content exceeded `_PLAIN_PREVIEW_BYTES` (16 KB) or 500 lines. An 18 KB Python file (`caffe2/.../dataio_test.py`) lost keyword coloring while a 4 KB sibling (`coverage.py`) kept it, which looked like a bug.
- **Decision:** Remove the 16 KB / 500-line plain fallback entirely; always run the lightweight per-line tokenizer since preview payloads are already capped at `PREVIEW_MAX_BYTES` (64 KB) / `PREVIEW_MAX_LINES` (2000).
- **Rationale:** The tokenizer takes ~0.03 s for a max-size (50 KB / 2000-line) preview and emits ~280 KB of HTML, which QML RichText handles fine; the 16 KB cutoff was arbitrary and produced inconsistent highlighting.
