# CLI reference

Same flags in TUI (pre-filled on launch) and plain CLI (`--no-tui` or non-TTY).

## Quick examples

```bash
srxy registry ./src
srxy registry ./src --no-tui
srxy revenue ./docs --json
srxy revenue ./docs --content-only
srxy budget . --format flat
srxy invoice ./photos --ocr --content-only
srxy "call me maybe" ~/Music --transcribe --content-only
srxy "dog at the beach" ~/Pictures --semantic-image --content-only
srxy revenue ./docs --semantic-all --content-only
```

Grouped output (default on plain CLI):

```
1 file matched for "registry"
── ./src/srxy/file_search.py ──
   match 82%  ·  matched: name, content
   line 128  ·  match 76%
   │ def «magic»_file_search(
```

## Boolean queries

`|` = OR, `&` = AND (`&` binds tighter). Multi-word OR phrases work without quotes; quote when operators appear inside phrases.

```bash
srxy 'alpha|beta' ./docs
srxy 'Linkin Park|Call Me' ~/Music --content-only
srxy '(red|blue|green)&color' ./docs
srxy '"my search text"|other' .
```

Each leaf matches content and names. `notes` does not auto-match filenames only.

Python equivalent: `FileQ.leaf("foo") & FileQ.leaf("bar")`. TUI query builder shows the equivalent CLI string.

## Scope

```bash
srxy token . --names-only
srxy token . --include-hidden
srxy token . --include-noise
```

Recursive walk. Default skips dot-hidden entries and noise dirs (`__pycache__`, `node_modules`).

## Flags

| | |
|---|---|
| **Scope** | `--names-only`, `--content-only`, `--names` / `--no-names`, `--content` / `--no-content` |
| **Matching** | `--threshold`, `--semantic-image-threshold`, `--transcribe-threshold`, `--semantic`, `--semantic-image`, `--semantic-all`, `--ocr`, `--transcribe` |
| **Limits** | `--max-file-size`, `--max-ocr-file-size`, `--max-transcribe-file-size`, `--max-matches`, `-l` / `--limit` |
| **Output** | `--format grouped\|flat`, `--json`, `-o` / `--output` |
| **Walk** | `--include-hidden`, `--include-noise` |
| **UX** | `--progress` / `--no-progress`, `--no-tui` |

`--max-line-matches` is deprecated; use `--max-matches`.

## Plain output

Progress bar on stderr when TTY; spinner during OCR/transcribe/CLIP/model load. Results print after scan, sorted by score. Skipped-file warnings after summary.

**Exit codes:** `0` matches, `1` none, `2` usage/path error.

## Supported formats

| Category | Formats | Searched | Notes |
|----------|---------|----------|-------|
| Plain text | any | line-by-line body | `--max-file-size` applies |
| Documents | `.pdf`, `.docx`, `.xlsx`, `.pptx` | extracted text | page / paragraph / row / slide |
| Images | `.jpg`, `.jpeg`, `.png`, `.webp`, `.tif`, `.tiff`, `.heic`, `.heif` | EXIF + metadata | |
| Camera RAW | `.arw`, `.cr2`, `.cr3`, `.dng`, `.nef`, … | EXIF from preview | CLIP via `rawpy` |
| Audio | `.mp3`, `.flac`, `.ogg`, `.oga`, `.opus`, `.m4a`, `.aac` | tags; speech with `--transcribe` | |
| Video | `.mp4`, `.m4v`, `.mov` | metadata; speech with `--transcribe` | |
| Video (limited) | `.mkv`, `.avi`, `.webm` | filename only | |
| Linux tags | any | xattrs (`xdg.tags`, etc.) | |
| macOS tags | any | Finder tags + comments | |
| Windows tags | any | `System.Keywords` | `srxy[windows]` |

Media metadata and OS tags ignore `--max-file-size`. No default cap on plain text or office docs. Binary-looking files (null in first 8 KiB) skip body text.

Optional layers: [Power-ups](power-ups.md) — OCR, text semantic, image semantic (CLIP), transcription.
