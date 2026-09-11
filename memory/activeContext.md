# Active Context

_Last updated: 2026-09-11_

## Branch

- `main` @ `182649f` — hotfix #49 merged (Windows Property Store isolation).
- `develop` / `feature/1.8.0` — packaging trunk / 1.8.0 release train (unchanged by this docs work).

## Current focus

README GUI screenshot: Search / Options / Filters chrome fixed in the export script.

## Just changed

- `scripts/docs/export_gui_screenshot.sh`:
  - Prefer real display; auto-fall back to `offscreen` + `QSG_RHI_BACKEND=software` when DISPLAY/Wayland are set but unreachable.
  - Wait for `frameSwapped` before `grabWindow`.
  - Assert Search/Options/Filters/Browse geometry; fail if Search accent fill is missing.
  - **Composite fallback:** when Material rounded-rect shaders omit fills from headless grabs, paint faces from QML `background.color`/`radius` and re-stamp label + Search icon (white on accent).
- `docs/images/gui-linux.png` — regenerated (1200×800) with visible blue Search (icon+label) and grey Options/Filters pills.

## Next steps

1. User may want to commit the script fix + `gui-linux.png` (not committed yet).
2. Optional: re-run `./scripts/docs/export_gui_screenshot.sh` on a real Linux display (no composite path) for a pixel-perfect Material grab; macOS/Windows tiles still need host regenerations.
3. Resume post-1.7.0 / 1.8.0 items when Daniel asks.
