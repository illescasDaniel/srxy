# macOS installer wrappers

Build two macOS `.app` wrappers that launch existing srxy installer flows:

- Offline: `Srxy <srxy-ver> - Installer <installer-ver>.app` (PySide wizard)
- Online: `Srxy <srxy-ver> - Installer Online <installer-ver>.app` (Go bootstrap + localhost UI)

Both installers target a user-owned prefix under `~/Applications/srxy` by default.

Third-party runtime binaries (tesseract, ffmpeg, …) are **not** embedded in these `.app` bundles. On Apple Silicon, the installer downloads pinned upstream artifacts at install time (Homebrew core bottles via `ghcr.io` for tesseract; martin-riedl builds for ffmpeg).

## Build

```bash
./packaging/macos/build-offline.sh
./packaging/macos/build-online.sh
```

Artifacts are emitted in `dist/` as:

- app bundles: `Srxy <ver> - Installer [Online] <installer_ver>.app` (local smoke)
- release DMGs: `srxy-<ver>-installer[-online]-<installer_ver>-<arch>.dmg`
- checksums: `SHA256SUMS-macos-*`, `*.sha256`

DMGs use UDZO compression and a Finder background with bottom-aligned text: **Double-click the installer**.

The offline build prunes unused PySide6/Qt frameworks after install (see `prune-pyside.sh`), while keeping the macOS Quick Controls style framework required at runtime.

## Smoke

```bash
./packaging/macos/smoke-offline.sh
./packaging/macos/smoke-online.sh
```
