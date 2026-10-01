# Active Context

_Last updated: 2026-10-01_

## Branch

- `feature/media-preview-panel` — polish committed (`5201dcb`); FFmpeg demuxer-silence follow-up uncommitted (awaiting Daniel `uv run task gui` confirm).

## Current focus

1. **FFmpeg `Input #0` silence** — those dumps are libavutil stderr from Qt Multimedia, not Qt logging categories. `silence_ffmpeg_av_log()` sets `av_log` to ERROR on PySide6's bundled `libavutil` (ctypes). Combined with newline `setFilterRules` for the LGPL category notice.
2. Unlimited OCR — not touched.

## Next steps

1. Daniel confirms GUI is quiet on video select; then commit the silence fix(es).
2. Visual smoke (poster + icons); undraft PR #39 when ready.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
