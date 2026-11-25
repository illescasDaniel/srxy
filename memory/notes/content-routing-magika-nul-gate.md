---
name: content-routing-magika-nul-gate
description: Add magika and content_kind.resolve_content_route: (1) NUL sample ⇒ never treat as UTF-8 body text even if Magika says is_text; (2) trust known media/doc…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Content search and preview were mis-handling extensionless Minecraft `assets/objects` hashes and wrong-extension files (e.g. mp4 named `.txt`, text named `.mp4`, lying `.pdf`). Basename/hash skips and suffix-only routing were rejected.
- **Decision:** Add `magika` and `content_kind.resolve_content_route`: (1) NUL sample ⇒ never treat as UTF-8 body text even if Magika says `is_text`; (2) trust known media/doc suffixes when parse/metadata works; (3) escalate to Magika for extensionless, parse failure, or text/media mismatch; (4) `DocumentExtractError` on doc parse failure so callers can re-route. Wire through `line_sources`, `document_text`, `media_metadata`, and preview payloads.
- **Rationale:** Content typing matches real bytes; Magika beats libmagic packaging pain. NUL-first avoids Magika false-positive text on tiny binary samples.
