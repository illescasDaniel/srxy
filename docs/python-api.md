# Python API

Import from `srxy` only — [`__init__.__all__`](../src/srxy/__init__.py) is the stable contract:

`magic_file_search`, `magic_search`, `search`, `Q`, `FileQ`, `FieldConfig`, `MatchType`, `SearchResult`, `FileSearchResult`, `LineMatch`, `SkippedFile`, `ActivityUpdate`

Generated signatures and docstrings: [api-reference.md](api-reference.md).

## File search

```python
from pathlib import Path
from srxy import FileQ, magic_file_search

results = magic_file_search(Path("./src"), "registry", threshold=0.3)
for result in results:
    print(result.path, result.score, result.breakdown)
    for line in result.lines:
        print(f"  line {line.line_number}: {line.text}")

results = magic_file_search(Path("."), "token", skip_hidden_folders=False)
results = magic_file_search(Path("."), "token", skip_noise_folders=False)
results = magic_file_search(Path("."), "token", skip_noise_files=False)
results = magic_file_search(Path("."), "uv.lock", match_skipped_names=True)
results = magic_file_search(Path("."), "token", include_archives=True)
results = magic_file_search(Path("."), "token", include_subdirectories=False)

# Boolean file query (same syntax as CLI)
results = magic_file_search(Path("./docs"), FileQ.leaf("foo") | FileQ.leaf("bar"))

# Power-ups and streaming callbacks
skipped: list = []
results = magic_file_search(
    Path("./photos"),
    "invoice",
    ocr=True,
    semantic_image=True,
    transcribe=True,
    limit=20,
    max_matches=10,
    max_file_size=50_000_000,
    skipped_files=skipped,
    on_progress=lambda current, total: None,
    on_activity=lambda update: None,
    on_result=lambda result: None,
)
```

Text semantic matching is enabled via env (`SRXY_SEMANTIC=1`) or the CLI; image semantic search uses the `semantic_image=` kwarg.

`--json` / file output include full matched line text — treat results as sensitive when sharing logs.

## In-memory search

`magic_search` — auto fields, composite matching, dicts/dataclasses/Pydantic. Default threshold `0.35`.

```python
from srxy import magic_search

items = [{"name": "salt"}, {"name": "salty"}, {"name": "salad"}]
results = magic_search(items, "salat", fields=["name"])
```

`search` + `Q` DSL for precision:

```python
from srxy import search, Q, FieldConfig, MatchType

search(items, "salat", where=Q.composite("name") | Q.contains("tags"))
search(items, "spatial", where=Q.all(Q.composite("name"), Q.exact("status")))
```

Boolean scoring: `OR` = `max(children)`, `AND` = `min(children)`.

## Match types

| Type | Behavior |
|------|----------|
| `EXACT` | Case-insensitive equality |
| `CONTAINS` | Substring |
| `PARTIAL` | Prefix/suffix |
| `FUZZY` | rapidfuzz similarity |
| `PHONETIC` | metaphone, soundex, NYSIIS |
| `SEMANTIC` | Meaning similarity (optional) |
| `COMPOSITE` | Weighted blend (default) |

Default composite weights: fuzzy 35%, semantic 20%, partial 15%, phonetic 12%, contains 10%, exact 8%. Semantic off → renormalize. Override via `composite_weights` on `Q.composite(...)` or `FieldConfig`.
