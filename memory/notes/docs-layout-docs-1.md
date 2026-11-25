---
name: docs-layout-docs-1
description: Docs now carry docs-1 frontmatter and are indexed from generated docs/INDEX.md instead of ad-hoc Markdown
type: decision
date: 2026-11-25
status: current
supersedes:
superseded_by:
source:
---

Every `docs/*.md` file now starts with docs-1 frontmatter (`id`, `title`, `summary`, `type`, `status`, `updated`, `verified`, `covers`, `related`), and `docs/INDEX.md` is generated from it by `docs_index.py write`. The generated `docs/api-reference.md` keeps the same frontmatter in `scripts/docs/export_public_api.py`'s `HEADER`, so regeneration preserves it.

**Why:** one index line per doc lets an agent choose a doc without opening it, and `covers` + `verified` make stale docs detectable when the code they describe changes.

**Rejected:** hand-maintained index lists (drift) and keeping docs without `covers` (no staleness check).

**How to apply:** start at `docs/INDEX.md`; run `docs_index.py covers <path>` before changing code; update the doc in the same change; run `docs_index.py write` and `docs_index.py check`. When `docs_index.py verify DOC-006` restamps `api-reference.md`, copy the same `verified` value into the generator `HEADER` or `tests/unit/test_public_api.py` fails on the regeneration comparison.
