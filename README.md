# Srxy

**Smart, composable search for Python — and your filesystem.**

Pass any list of objects (dicts, dataclasses, Pydantic models) and find what you mean, not just what you typed. Fuzzy, phonetic, and composite matching out of the box. Search files by name or content from Python or the terminal.

## Installation

**Use as a library** (in a project or virtualenv):

```bash
pip install srxy
```

**Use the CLI globally** (recommended for terminal use):

```bash
pipx install srxy
```

If you don't have pipx yet, see the [pipx installation guide](https://pipx.pypa.io/stable/installation/).

---

## Why Srxy?

| | |
|---|---|
| **Magic search** | One function call. Auto-discovers fields, blends matchers, ranks by score. |
| **Field search + AND/OR** | Per-field strategies with a fluent `Q` DSL — combine conditions with `&` and `\|`. |
| **File search + CLI** | Search paths by file name and/or content. Same smart matching, plus a `srxy` command. |

---

## Magic search

The fastest path to good results. `magic_search` auto-discovers fields from your items, runs composite matching on each, and keeps the best score (OR semantics). Typos, phonetic near-misses, and partial matches are handled for you.

```python
from srxy import magic_search

items = [
    {"name": "salt"},
    {"name": "salty"},
    {"name": "salad"},
]

# Match across specific fields
results = magic_search(items, "salat", fields=["name"])
print(results[0].item["name"])  # salad
print(results[0].score)

# Or search every discoverable field (default)
results = magic_search(items, "salat")
```

Works with dicts, dataclasses, and Pydantic models. Default threshold is `0.25`; tune it when you need stricter or looser matches.

---

## Field search with AND / OR

When you need precision, use `search` with the `Q` expression DSL. Pick a match strategy per field, then wire them together with boolean logic.

```python
from srxy import search, Q, FieldConfig, MatchType

# OR — match if any field scores well
search(items, "salat", where=Q.composite("name") | Q.contains("tags"))

# AND — every branch must clear the threshold
search(items, "spatial", where=Q.all(Q.composite("name"), Q.exact("status")))

# Nested — (sku OR barcode) AND label
search(
    items,
    "ABC-123",
    where=Q.any(Q.exact("sku"), Q.exact("barcode")) & Q.exact("label"),
)
```

Boolean scoring: `OR` uses `max(child scores)`, `AND` uses `min(child scores)`.

Prefer explicit config over the DSL? Pass a list of `FieldConfig` instead:

```python
search(
    people,
    "engineer",
    fields=[
        FieldConfig("role", MatchType.EXACT, weight=2.0),
        FieldConfig("name", MatchType.CONTAINS, weight=1.0),
    ],
    threshold=0.5,
)
```

---

## File search

Search filesystem paths by **file name**, **file content**, or both — no ML required. Directories are walked recursively. By default, dot-prefixed hidden entries and noise folders (`__pycache__`, `node_modules`) are skipped. Content search scores each line and returns matching line numbers.

Supported content formats: plain text, `.pdf`, `.docx`, `.xlsx`, and `.pptx` (text extracted automatically).

```python
from pathlib import Path
from srxy import magic_file_search

results = magic_file_search(Path("./src"), "registry", threshold=0.3)
for result in results:
    print(result.path, result.score, result.breakdown)
    for line in result.lines:
        print(f"  line {line.line_number}: {line.text}")

# Include hidden directories and files (e.g. .git)
results = magic_file_search(Path("."), "token", skip_hidden_folders=False)

# Include noise directories (e.g. __pycache__, node_modules)
results = magic_file_search(Path("."), "token", skip_noise_folders=False)

# Search everywhere — disable both skip flags
results = magic_file_search(
    Path("."),
    "token",
    skip_hidden_folders=False,
    skip_noise_folders=False,
)
```

### CLI

Install with [pipx](https://pipx.pypa.io/) for a global `srxy` command (`pipx install srxy`), then search from the terminal:

```bash
# Search names and contents (grouped output)
srxy registry ./src

# Content only — shows line numbers
srxy revenue ./docs --content-only

# Flat, pipe-friendly output
srxy token ./src --format flat

# JSON for scripting
srxy budget . --json

# Search hidden directories and files (e.g. .git)
srxy token . --include-hidden

# Search noise directories (e.g. __pycache__, node_modules)
srxy token . --include-noise

# Search everywhere
srxy token . --include-hidden --include-noise
```

Options: `--names-only`, `--content-only`, `--include-hidden`, `--include-noise`, `--threshold`, `--max-file-size`, `--max-line-matches`, `--semantic` (opt-in ML). Exit codes: `0` matches found, `1` no matches, `2` usage/path error.

---

## Match types

| Type | Behavior |
|------|----------|
| `EXACT` | Case-insensitive full string equality |
| `CONTAINS` | Substring match |
| `PARTIAL` | Prefix or suffix match |
| `FUZZY` | Character-level similarity (rapidfuzz) |
| `PHONETIC` | Sounds-alike (metaphone, soundex, NYSIIS with graduated scoring) |
| `SEMANTIC` | Meaning similarity (optional; see below) |
| `COMPOSITE` | Weighted blend of available atomic matchers (default smart mode) |

Default composite weights: fuzzy 35%, semantic 20%, partial 15%, phonetic 12%, contains 10%, exact 8%. When semantic is disabled, composite skips it and renormalizes the remaining weights. Override per field via `composite_weights` on `Q.composite(...)` or `FieldConfig`.

---

## Semantic matching (optional)

Semantic search is **off by default**. Opt in when you need meaning-based similarity:

```bash
export SRXY_SEMANTIC=1
pip install 'srxy[semantic]'   # or: pipx install 'srxy[semantic]'
```

With `SRXY_SEMANTIC=1`, composite matching includes semantic similarity. Explicit `Q.semantic(...)` or `MatchType.SEMANTIC` raises a clear error if semantic is not enabled.

Default model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (downloaded from Hugging Face on first use). For a local cache:

```bash
./scripts/download_semantic_model.sh
export SRXY_SEMANTIC_MODEL_PATH=~/.cache/srxy/semantic-model
```

Core dependencies (always installed): `rapidfuzz` and `jellyfish` (phonetic matching).

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,semantic]"
./scripts/quality/checks.sh --fix
./scripts/quality/checks.sh
```

Quality gate: Ruff → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

- **Local** (`./scripts/quality/checks.sh`): runs all tests (unit + integration).
- **CI**: runs only `pytest -m unit` (fast tests; no semantic model required).

Integration tests (requires `pip install -e ".[semantic]"` and `SRXY_SEMANTIC=1`, set automatically in `tests/integration/conftest.py`):

```bash
pytest -m integration
```

Integration tests load a curated news-style corpus from `tests/fixtures/search_corpus.json` and measure top-k hit rates.
