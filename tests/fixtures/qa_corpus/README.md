# QA test corpus

Binary fixtures for release QA and integration tests. **Dev-only** — not installed with the `srxy` package (setuptools packages only `src/`).

Override path with `SRXY_QA_CORPUS` if needed.

## Layout

| Path | Purpose |
|------|---------|
| `docs/notes.txt` | Text search (`axolotl`) |
| `docs/minimal.{jpg,mp3,mp4}` | Fast semantic-image / metadata smoke |
| `docs/ocr/` | OCR PDF/PNG fixtures |
| `docs/folder.jpg` | Real-world OCR (composer credits) |
| `docs/IMG_20260223_184931.jpg` | Semantic image (`person`) |
| `IMG_20260222_181128.mp4` | Quiet phone video → transcribe fallback |
| `qa_downloads/` | Office docs, generated OCR PNG, sample images/audio |

## Regenerating

If you have the original scratch corpus, sync with:

```bash
SRC=/path/to/temp_docs
DST=tests/fixtures/qa_corpus
cp "$SRC/docs/notes.txt" "$DST/docs/"
cp tests/fixtures/minimal.* "$DST/docs/"
cp -r tests/fixtures/ocr "$DST/docs/"
cp "$SRC/docs/"*.jpg "$DST/docs/"
cp "$SRC/IMG_20260222_181128.mp4" "$DST/"
cp -r "$SRC/qa_downloads/"{documents,ocr,images,audio} "$DST/qa_downloads/"
```
