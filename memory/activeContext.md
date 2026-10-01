# Active Context

_Last updated: 2026-10-01_

## Branch

- `feature/media-preview-panel` @ fixing Ubuntu CI: avutil ctypes OSError in silence test (not pinTop).

## Current focus

1. **Ship PR #39** — Ubuntu `quality` fails on `test_given_pyside_avutil_when_silencing_ffmpeg_av_log_then_sets_error_level` (OPENSSL_3.0.0 / RAND_bytes); skip when not ctypes-loadable.
2. Unlimited OCR — not touched.

## Next steps

1. Push avutil test fix; on CI green squash-merge; pull `feature/1.8.0`.

## Memory protocol (2026-09-01)

- `agent-memory.mdc`: never record worktree deletion/cleanup in tracked memory.
