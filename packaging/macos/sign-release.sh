#!/usr/bin/env bash
# Locally sign, notarize, and staple a macOS installer .app, then repackage it
# into a signed + notarized .dmg.
#
# Local-only: CI never runs this and never sees the certificate. Secrets are
# read from packaging/macos/signing/signing.env (gitignored) — see
# packaging/macos/signing.env.example for the template and one-time setup steps.
#
# Usage: ./packaging/macos/sign-release.sh <app-bundle> <output-dmg> [volume-name]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SIGNING_DIR="$ROOT/packaging/macos/signing"
ENV_FILE="$SIGNING_DIR/signing.env"
ENTITLEMENTS="$ROOT/packaging/macos/entitlements.plist"

if [[ "$(uname -s)" != "Darwin" ]]; then
	echo "error: signing must run on Darwin" >&2
	exit 1
fi
if [[ $# -lt 2 || $# -gt 3 ]]; then
	echo "usage: $0 <app-bundle> <output-dmg> [volume-name]" >&2
	exit 2
fi

APP_BUNDLE="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUT_DMG="$2"
VOL_NAME="${3:-srxy Installer}"

if [[ ! -d "$APP_BUNDLE" ]]; then
	echo "error: app bundle not found: $APP_BUNDLE" >&2
	exit 1
fi
if [[ ! -f "$ENTITLEMENTS" ]]; then
	echo "error: missing entitlements file: $ENTITLEMENTS" >&2
	exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
	echo "error: missing $ENV_FILE" >&2
	echo "copy packaging/macos/signing.env.example to $ENV_FILE and fill it in." >&2
	exit 1
fi
for tool in codesign xcrun security ditto openssl; do
	if ! command -v "$tool" >/dev/null 2>&1; then
		echo "error: required tool not found: $tool" >&2
		exit 1
	fi
done

# shellcheck disable=SC1090
source "$ENV_FILE"
for var in SRXY_SIGNING_IDENTITY SRXY_SIGNING_P12 SRXY_SIGNING_P12_PASSWORD SRXY_NOTARY_PROFILE; do
	if [[ -z "${!var:-}" ]]; then
		echo "error: $var is not set in $ENV_FILE" >&2
		exit 1
	fi
done

P12_PATH="$SIGNING_DIR/$SRXY_SIGNING_P12"
if [[ ! -f "$P12_PATH" ]]; then
	echo "error: certificate not found: $P12_PATH" >&2
	exit 1
fi

KEYCHAIN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/srxy-signing.XXXXXX")"
KEYCHAIN_PATH="$KEYCHAIN_DIR/signing.keychain-db"
KEYCHAIN_PASSWORD="$(openssl rand -base64 32)"
NOTARIZE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/srxy-notarize.XXXXXX")"

ORIGINAL_KEYCHAINS=()
while IFS= read -r kc; do
	ORIGINAL_KEYCHAINS+=("$kc")
done < <(security list-keychains -d user | sed 's/^ *"//; s/" *$//')

cleanup() {
	if [[ ${#ORIGINAL_KEYCHAINS[@]} -gt 0 ]]; then
		security list-keychains -d user -s "${ORIGINAL_KEYCHAINS[@]}" >/dev/null 2>&1 || true
	fi
	security delete-keychain "$KEYCHAIN_PATH" >/dev/null 2>&1 || true
	rm -rf "$KEYCHAIN_DIR" "$NOTARIZE_DIR"
}
trap cleanup EXIT

echo "Creating temporary signing keychain…"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security import "$P12_PATH" -k "$KEYCHAIN_PATH" -P "$SRXY_SIGNING_P12_PASSWORD" -T /usr/bin/codesign -T /usr/bin/security
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH" >/dev/null
security list-keychains -d user -s "$KEYCHAIN_PATH" "${ORIGINAL_KEYCHAINS[@]}"

sign() {
	codesign --force --options runtime --timestamp --keychain "$KEYCHAIN_PATH" --sign "$SRXY_SIGNING_IDENTITY" "$@"
}

# Apple's inside-out signing order: nested dylibs/frameworks/executables first
# (no special entitlements needed — those only matter for the process that
# actually dlopen()s things at runtime), then the executable(s) that load them,
# then the outer bundle. `--deep` alone tends to mis-order or skip edge cases
# for mixed-origin Python/Qt payloads, so we walk the tree explicitly.
echo "Signing nested dylibs/.so under ${APP_BUNDLE}…"
while IFS= read -r -d '' item; do
	sign "$item"
done < <(find "$APP_BUNDLE" \( -name "*.dylib" -o -name "*.so" \) -type f -print0)

echo "Signing nested frameworks under ${APP_BUNDLE}…"
while IFS= read -r -d '' fw; do
	sign "$fw"
done < <(find "$APP_BUNDLE" -name "*.framework" -type d -print0)

echo "Signing nested executables under $APP_BUNDLE/Contents/Resources…"
if [[ -d "$APP_BUNDLE/Contents/Resources" ]]; then
	while IFS= read -r -d '' exe; do
		if file "$exe" | grep -q "Mach-O"; then
			sign --entitlements "$ENTITLEMENTS" "$exe"
		fi
	done < <(find "$APP_BUNDLE/Contents/Resources" -type f -perm -111 -print0)
fi

echo "Signing ${APP_BUNDLE}…"
sign --deep --entitlements "$ENTITLEMENTS" "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

echo "Zipping for notarization…"
ZIP_PATH="$NOTARIZE_DIR/$(basename "$APP_BUNDLE" .app).zip"
ditto -c -k --keepParent "$APP_BUNDLE" "$ZIP_PATH"

echo "Submitting app to notarytool (this can take a few minutes)…"
xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$SRXY_NOTARY_PROFILE" --wait

echo "Stapling notarization ticket to ${APP_BUNDLE}…"
xcrun stapler staple "$APP_BUNDLE"

echo "Rebuilding DMG with the signed + stapled app…"
"$ROOT/packaging/macos/build-dmg.sh" "$APP_BUNDLE" "$OUT_DMG" "$VOL_NAME"

echo "Signing ${OUT_DMG}…"
codesign --force --timestamp --keychain "$KEYCHAIN_PATH" --sign "$SRXY_SIGNING_IDENTITY" "$OUT_DMG"

echo "Submitting DMG to notarytool…"
xcrun notarytool submit "$OUT_DMG" --keychain-profile "$SRXY_NOTARY_PROFILE" --wait

echo "Stapling notarization ticket to ${OUT_DMG}…"
xcrun stapler staple "$OUT_DMG"

echo
echo "Verifying…"
codesign -dv --verbose=2 "$APP_BUNDLE" 2>&1 | sed 's/^/  /'
spctl -a -vv "$APP_BUNDLE" 2>&1 | sed 's/^/  /'
spctl -a -vv --type open --context context:primary-signature "$OUT_DMG" 2>&1 | sed 's/^/  /'

echo
echo "Signed + notarized: $APP_BUNDLE"
echo "Signed + notarized: $OUT_DMG"
