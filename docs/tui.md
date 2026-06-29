# Interactive TUI

On an interactive terminal (no `--json`, `--format flat`, or `-o`), srxy opens a **Textual** full-screen TUI by default.

![srxy TUI](images/tui.png)

## Layout

| Area | What it shows |
|------|----------------|
| **Query / Path** | Search string and root directory; **Search** runs the scan |
| **Options** | Names, Content, Semantic, Image semantic, OCR, Transcribe, Hidden, Noise |
| **Filters** | **Top files** (`-l` / `--limit`) and **Per file** (`--max-matches`) |
| **Results** | Sortable table: match %, path, sources (`name`, `content`, `ocr`, `transcript`, `tag`, …) |
| **Preview** | Selected file path, score, sources, hit table (location + **bold** query highlights) |
| **Status** | Progress, match count, copy buttons (**Path**, **Match**, **All**) |

Heavy modes run in a background worker so the UI stays responsive.

## Workflow

1. Enter query and path (or launch with args pre-filled).
2. Toggle options/filters; **Search**, **Enter**, or **Ctrl+S**.
3. **j** / **k** (or arrows) through results — preview updates.
4. **o** opens the selected file in the OS default app.

Changing query, path, options, or filters after a search marks **Search** **orange** (stale results).

## Clipboard

| Key | Button | Copies |
|-----|--------|--------|
| `y` | **Path** | Absolute path of selected result |
| `m` | **Match** | Focused preview row |
| `M` | **All** | Every preview row for the file |

Uses OSC 52; most modern terminals support it.

## Keybindings

| Keys | Action |
|------|--------|
| `Enter`, `Ctrl+S` | Run search |
| `/` | Focus query |
| `j` / `k` | Move selection |
| `o` | Open file |
| `y`, `m`, `M` | Copy path / match / all |
| `?` | Help |
| `q`, `Ctrl+C` | Quit |

## When the TUI is skipped

Plain CLI when: **`--no-tui`**, **`--json`**, **`--format flat`**, **`-o`**, or stdout is **not a TTY**.

## Manual release checklist

Automated coverage: `pytest tests/tui/`. On a **real TTY** before release:

| Check | Verify |
|-------|--------|
| Scope toggles | Content off, Names on — results respect scope |
| OCR | Enable OCR on photos/PDFs — UI stays responsive |
| Transcribe | Enable on audio/video — UI stays responsive |
| Clipboard | `y` / `m` / `M` copy (OSC 52) |
| Open file | `o` opens in default app |
| Resize | Layout stays usable |
| Missing tesseract | Preflight shows clear error |

```bash
srxy ./tests/fixtures/file_search
srxy "axolotl" ./tests/fixtures/file_search
```

Regenerate the screenshot: `./scripts/docs/export_tui_screenshot.sh`
