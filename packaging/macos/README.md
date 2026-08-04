# macOS installer wrappers

Build two macOS `.app` wrappers that launch existing srxy installer flows:

- `srxy-installer-offline.app`: PySide wizard (`srxy.adapters.inbound.installer`)
- `srxy-installer-online.app`: Go bootstrap + localhost web installer (`srxy.adapters.inbound.installer_online`)

Both installers target a user-owned prefix under `~/Applications/srxy` by default.

Third-party runtime binaries (tesseract, ffmpeg, …) are **not** embedded in these `.app` bundles. On Apple Silicon, the installer downloads pinned upstream artifacts at install time (Homebrew core bottles via `ghcr.io` for tesseract; martin-riedl builds for ffmpeg).

## Build

```bash
./packaging/macos/build-offline.sh
./packaging/macos/build-online.sh
```

Artifacts are emitted in `dist/` as:

- app bundles: `srxy-installer-*.app`
- release archives: `*.app.tar.gz`
- checksums: `SHA256SUMS-macos`, `*.sha256`

## Smoke

```bash
./packaging/macos/smoke-offline.sh
./packaging/macos/smoke-online.sh
```
