---
name: preview-owns-qtextdocument
description: Store QQuickTextDocument, re-resolve live QTextDocument via textDocument() + shiboken6.isValid, apply content with setPlainText (Python-owned), drop QML…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Rapid GUI selection left preview on “Loading…” with `RuntimeError: libshiboken: Internal C++ object (QTextDocument) already deleted` in `_apply_preview_document` / `_refresh_preview_line_height`.
- **Decision:** Store `QQuickTextDocument`, re-resolve live `QTextDocument` via `textDocument()` + `shiboken6.isValid`, apply content with `setPlainText` (Python-owned), drop QML `text: controller.previewText` binding, always `previewChanged.emit()` after display updates, and estimate line height with a fixed constant (no `documentLayout()`/`defaultFont()` under shiboken).
- **Rationale:** QML TextArea can replace the C++ document while a worker result still holds a stale pointer; writing through the live Quick document and not dual-binding text stops the lifetime crash and stuck Loading.
