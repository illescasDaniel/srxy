# macOS installer wrappers

Build two macOS `.app` wrappers that launch existing srxy installer flows:

- Offline: `Srxy <srxy-ver> - Installer <installer-ver>.app` (PySide wizard)
- Online: `Srxy <srxy-ver> - Installer Online <installer-ver>.app` (Go bootstrap + localhost UI)

Both installers target a user-owned prefix under `~/Applications/srxy` by default.

Third-party runtime binaries (tesseract, ffmpeg, …) are **not** embedded in these `.app` bundles. On Apple Silicon, the installer downloads pinned upstream artifacts at install time (Homebrew core bottles via `ghcr.io` for tesseract; martin-riedl builds for ffmpeg).

The installed `Srxy.app` Dock/Finder icon uses squircle-masked artwork under [`src/srxy/resources/icons/macos/`](../../src/srxy/resources/icons/macos/) (master: `srxy.png`), laid out on Apple’s 1024 canvas with an 824 art box (~100 px gutter). The uncompressed original lives at [`assets/icons/srxy.png`](../../assets/icons/srxy.png). Regenerate packaged icons after changing the original:

```bash
task generate-installer-icons   # square + installer badge into src/…
task generate-macos-icons       # squircle-masked macOS set into src/…/macos/
```

## Build (unsigned — matches CI)

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

The offline build's bundled venv is made relocatable: `venv/bin/python*` are rewritten to symlinks relative to the venv, and `pyvenv.cfg`'s `home` is rewritten relative too, with build-time checks that fail closed if either still resolves outside the `.app` (or into the build host's `~/.local/share/uv/python/` cache). Without this, the bundled interpreter only works on the machine that built it. This mirrors [`packaging/linux-appimage/build.sh`](../linux-appimage/build.sh)'s AppDir relocation fix.

These unsigned builds are what GitHub Actions produces (see [`.github/workflows/macos-installer.yml`](../../.github/workflows/macos-installer.yml)) — no certificate ever touches CI. Unsigned/unnotarized apps hit macOS Gatekeeper friction: on first launch, `com.apple.quarantine` triggers a `syspolicyd` consent check that can hang the process indefinitely (observed via `sample` stuck at `_dyld_start` with 0% CPU) if it can't get a response, rather than failing fast. Sign locally (below) before distributing to end users.

## Build (locally signed + notarized — for website distribution)

CI never signs anything. If you're distributing installers yourself (e.g. from your own website) and have a paid Apple Developer Program membership, sign and notarize locally:

1. One-time setup:
   - In Xcode → Settings → Accounts → (your team) → Manage Certificates, create a **Developer ID Application** certificate, then export it from Keychain Access as a `.p12` (set a password on export).
   - Set up a `notarytool` keychain profile (stored in your login keychain, not on disk):
     ```bash
     xcrun notarytool store-credentials srxy-notary \
       --apple-id "you@example.com" \
       --team-id "TEAMID1234" \
       --password "an app-specific password from appleid.apple.com"
     ```
   - Copy [`packaging/macos/signing.env.example`](signing.env.example) to `packaging/macos/signing/signing.env` and fill in `SRXY_SIGNING_IDENTITY`, `SRXY_SIGNING_P12`, `SRXY_SIGNING_P12_PASSWORD`, `SRXY_NOTARY_PROFILE`. Put the exported `.p12` at `packaging/macos/signing/<name>.p12`. **`packaging/macos/signing/` is gitignored** — nothing under it is ever committed or read by CI.

2. Build + sign + notarize + staple:
   ```bash
   ./packaging/macos/build-offline-signed.sh
   ./packaging/macos/build-online-signed.sh
   ```
   Each script builds the unsigned `.app` (identical to CI), then hands off to [`sign-release.sh`](sign-release.sh), which:
   - Signs nested `.dylib`/`.so`/`.framework` payloads and executables inside-out with a Developer ID identity and hardened runtime, applying [`entitlements.plist`](entitlements.plist) (disables library validation — required because the bundled CPython/Qt payload isn't signed with the same identity) to the executables that actually load them.
   - Notarizes the `.app` (`xcrun notarytool submit --wait`) and staples the ticket.
   - Rebuilds the `.dmg` around the signed + stapled `.app`, signs the `.dmg`, notarizes it, and staples it too.
   - Imports the `.p12` into a throwaway temporary keychain for the duration of the run only; your login keychain is never touched.

Run `./packaging/macos/sign-release.sh <app-bundle> <output-dmg> [volume-name]` directly if you already have an unsigned `.app` built and just want to (re)sign it.

## Smoke

```bash
./packaging/macos/smoke-offline.sh
./packaging/macos/smoke-online.sh
```

`smoke-offline.sh` copies the built `.app` to an unrelated temp path before testing, specifically to catch a non-relocatable bundled venv (the class of bug that shipped in v1.6.4 — CI's smoke test passed there because it ran against the build tree, where the broken absolute symlinks still happened to resolve).
