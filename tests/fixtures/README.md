# Test fixtures

Dev-only assets for pytest. Not installed with the `srxy` package.

| Path | Purpose |
|------|---------|
| `corpus/` | In-memory semantic search eval (`search_corpus.json`, `labeled_queries.json`) |
| `file_search/` | Filesystem fixtures for `magic_file_search` integration tests |
| `file_search/minimal.{jpg,mp3,mp4}` | Tiny media for unit tests (`copy_media_fixture`) and file-search smoke |
| `file_search/ocr/` | OCR PDF/PNG fixtures (`revenue`, `classifier` tokens) |
| `file_search/samples/` | Office docs, OCR/images/audio format coverage, edge-case files |
| `file_search/samples/images/photoshop_xmp.jpg` | Sanitized JPEG with EXIF+XMP (fake author/software); XMP parsing / SIG regression tests |
| `file_search/samples/audio/` | `speech_sample.mp3` for transcribe integration tests |

Regenerate office documents or token images with helpers in `tests/helpers.py` (`write_docx_with_text`, etc.). Regenerate `photoshop_xmp.jpg` with `python scripts/fixtures/build_photoshop_xmp_fixture.py --source <path-to-sample1.png>` (sanitization applied automatically).

Override the search tree with `SRXY_FILE_SEARCH_FIXTURES`.
