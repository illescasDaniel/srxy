---
name: video-preview-poster-and-ffmpeg-log-silence
description: (1) Extend resolve_media_preview to a 3-tuple (kind, media_url, poster_url); for video, best-effort extract a first-frame PNG data: URI via ffmpeg…
type: decision
date: 2026-10-01
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Media preview panel showed a black `VideoOutput` until play; play/pause/mute were text labels; Qt logged `qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version … LGPL …` on every GUI launch that loads multimedia.
- **Decision:** (1) Extend `resolve_media_preview` to a 3-tuple `(kind, media_url, poster_url)`; for video, best-effort extract a first-frame PNG `data:` URI via `ffmpeg` (install-prefix binary or PATH, 10s timeout, `-loglevel quiet` + stderr discarded) into `previewPosterUrl`, shown as an `Image` overlay until `MediaPlayer` is Playing. If ffmpeg is missing, QML briefly play+pause (muted) to paint a frame into `VideoOutput`. (2) Play/pause/mute are icon-only `ToolButton`s (`qml/images/{play,pause,volume,volume-mute}.svg`) with ToolTips. (3) Silence Qt categories via `silence_noisy_qt_logging` (`qt.qpa.mime`, `qt.multimedia.ffmpeg`) with **newline**-separated `QLoggingCategory.setFilterRules` (a `;`-joined string is one malformed rule and ignored). (4) Raw demuxer dumps (`Input #0, mov,mp4…`) bypass Qt categories — lower FFmpeg `av_log` to ERROR on PySide6's bundled `libavutil` via `silence_ffmpeg_av_log()` (ctypes).
- **Rationale:** Poster extraction reuses optional ffmpeg without adding Qt/video decode deps to the Qt-free `media_preview` module. The LGPL line is a Qt category notice; the `Input #0` spam is libavutil stderr — both are backend noise, not app errors.
