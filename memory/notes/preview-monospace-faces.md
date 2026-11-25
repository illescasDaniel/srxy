---
name: preview-monospace-faces
description: Emit platform-specific faces from preview_font_family() in preview HTML (Windows Consolas, macOS Menlo, else monospace), matching QML. Do not suppress…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Opening some file previews on Windows logged `DirectWrite: CreateFontFaceFromHDC() failed` for `8514oem` / `Fixedsys` (`styleHint=5` TypeWriter), then cascades of `OpenType support missing` while Qt probed Tahoma/Arial/CJK/emoji fallbacks. Preview HTML forced `font-family:monospace` while QML already set Consolas/Menlo on the `TextArea`.
- **Decision:** Emit platform-specific faces from `preview_font_family()` in preview HTML (Windows `Consolas`, macOS `Menlo`, else `monospace`), matching QML. Do not suppress `qt.qpa.fonts` / `qt.text.font.db`, and do not switch to FreeType/`nodirectwrite`.
- **Rationale:** Bare CSS `monospace` on Windows maps to legacy bitmap fonts DirectWrite cannot load; naming a real TrueType face stops that cascade. Log filtering would hide real font issues; FreeType would change global text rendering.
